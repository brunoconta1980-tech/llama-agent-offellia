#include "agent-resources.h"

#include <cstdlib>
#include <filesystem>
#include <string>

#if defined(_WIN32)
#ifndef NOMINMAX
#define NOMINMAX
#endif
#include <windows.h>
#elif defined(__APPLE__)
#include <mach-o/dyld.h>
#include <cstdint>
#include <climits>
#include <vector>
#else
#include <unistd.h>
#endif

namespace fs = std::filesystem;

// Directory that contains the running llama-agent or llama-agent-server binary.
// Bundled skills are copied next to that binary at build time.
static std::string agent_executable_directory() {
#if defined(_WIN32)
    wchar_t buf[32768] = { 0 };
    DWORD len = GetModuleFileNameW(nullptr, buf, 32768);
    if (len == 0 || len >= 32768) {
        return "";
    }
    return fs::path(buf).parent_path().string();
#elif defined(__APPLE__)
    char small_path[PATH_MAX];
    uint32_t size = sizeof(small_path);
    if (_NSGetExecutablePath(small_path, &size) == 0) {
        std::error_code ec;
        fs::path exe = fs::weakly_canonical(fs::path(small_path), ec);
        if (ec) {
            exe = fs::path(small_path);
        }
        return exe.parent_path().string();
    }
    std::vector<char> buf(size);
    if (_NSGetExecutablePath(buf.data(), &size) != 0) {
        return "";
    }
    std::error_code ec;
    fs::path exe = fs::weakly_canonical(fs::path(buf.data()), ec);
    if (ec) {
        exe = fs::path(buf.data());
    }
    return exe.parent_path().string();
#else
    char path[4096];
    ssize_t count = ::readlink("/proc/self/exe", path, sizeof(path) - 1);
    if (count <= 0) {
        return "";
    }
    path[count] = '\0';
    return fs::path(path).parent_path().string();
#endif
}

std::string agent_resource_discovery::skills_prompt_section() const {
    return skills.generate_prompt_section();
}

std::string agent_resource_discovery::agents_md_prompt_section() const {
    return agents_md.generate_prompt_section();
}

std::vector<std::string> agent_build_skill_search_paths(
        const std::string & working_dir,
        const std::string & config_dir,
        const std::vector<std::string> & extra_paths) {
    const std::string search_working_dir = working_dir.empty() ? "." : working_dir;

    std::vector<std::string> skill_paths;

    // Project-local skills have highest priority.
    skill_paths.push_back(search_working_dir + "/.llama-agent/skills");
    skill_paths.push_back(search_working_dir + "/.agents/skills");

    if (!config_dir.empty()) {
        skill_paths.push_back(config_dir + "/skills");
    }

#ifdef _WIN32
    const char * home_skills = std::getenv("APPDATA");
    if (home_skills) {
        skill_paths.push_back(std::string(home_skills) + "\\agents\\skills");
    }
#else
    const char * home_skills = std::getenv("HOME");
    if (home_skills) {
        skill_paths.push_back(std::string(home_skills) + "/.agents/skills");
    }
#endif

    // Skills shipped with the binary. Project and user directories above win
    // when the same skill name exists in more than one place.
    const std::string exe_dir = agent_executable_directory();
    if (!exe_dir.empty()) {
        skill_paths.push_back((fs::path(exe_dir) / "skills").string());
    }

    skill_paths.insert(skill_paths.end(), extra_paths.begin(), extra_paths.end());

    return skill_paths;
}

agent_resource_discovery agent_discover_resources(const agent_resource_config & config) {
    const std::string working_dir = config.working_dir.empty() ? "." : config.working_dir;

    agent_resource_discovery discovery;

    if (config.enable_skills) {
        const std::vector<std::string> skill_paths = agent_build_skill_search_paths(
                working_dir, config.config_dir, config.extra_skills_paths);
        discovery.skills_count = discovery.skills.discover(skill_paths);
    }

    if (config.enable_agents_md) {
        discovery.agents_md_count = discovery.agents_md.discover(working_dir, config.config_dir);
        discovery.agents_md_total_content_size = discovery.agents_md.total_content_size();
    }

    return discovery;
}
