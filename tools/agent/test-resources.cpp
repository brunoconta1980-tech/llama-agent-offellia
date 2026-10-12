#include "agent-resources.h"
#include "skills/skills-manager.h"

#include <cassert>
#include <cstdio>
#include <filesystem>
#include <fstream>
#include <set>
#include <string>

namespace fs = std::filesystem;

static void test_skill_search_path_order() {
    const std::vector<std::string> paths = agent_build_skill_search_paths(
            "/work", "/cfg", {"/extra-one", "/extra-two"});

    assert(paths.size() >= 5);
    assert(paths[0] == "/work/.llama-agent/skills");
    assert(paths[1] == "/work/.agents/skills");
    assert(paths[2] == "/cfg/skills");
    assert(paths[paths.size() - 2] == "/extra-one");
    assert(paths[paths.size() - 1] == "/extra-two");

    printf("  PASS: skill_search_path_order\n");
}

static void test_empty_working_dir_defaults_to_current_dir() {
    const std::vector<std::string> paths = agent_build_skill_search_paths(
            "", "", {"/extra"});

    assert(paths.size() >= 3);
    assert(paths[0] == "./.llama-agent/skills");
    assert(paths[1] == "./.agents/skills");
    assert(paths[paths.size() - 1] == "/extra");

    printf("  PASS: empty_working_dir_defaults_to_current_dir\n");
}

static bool ends_with_skills_dir(const std::string & path) {
    return path.size() >= 7 &&
           (path.compare(path.size() - 7, 7, "/skills") == 0 ||
            path.compare(path.size() - 7, 7, "\\skills") == 0);
}

static void test_executable_skills_directory_is_before_extras() {
    const std::vector<std::string> paths = agent_build_skill_search_paths(
            "/work", "/cfg", {"/extra-one", "/extra-two"});

    assert(paths.size() >= 6);
    assert(ends_with_skills_dir(paths[paths.size() - 3]));
    assert(paths[paths.size() - 3].find(".llama-agent") == std::string::npos);
    assert(paths[paths.size() - 3].find(".agents") == std::string::npos);
    assert(paths[paths.size() - 2] == "/extra-one");
    assert(paths[paths.size() - 1] == "/extra-two");

    printf("  PASS: executable_skills_directory_is_before_extras\n");
}

static void test_bundled_skills_parse_when_present() {
    const std::vector<std::string> paths = agent_build_skill_search_paths(".", "", {});
    std::string bundled;
    for (const auto & path : paths) {
        if (!ends_with_skills_dir(path)) {
            continue;
        }
        if (path.find(".llama-agent") != std::string::npos || path.find(".agents") != std::string::npos) {
            continue;
        }
        bundled = path;
    }
    if (bundled.empty() || !fs::exists(bundled)) {
        printf("  SKIP: bundled_skills_parse_when_present\n");
        return;
    }

    const std::set<std::string> expected = {
        "build-with-ai",
        "create-skill",
        "create-workflow",
        "design",
        "docx",
        "execute-plan",
        "game-assets",
        "learn",
        "long-running-background-tasks",
        "pdf",
        "pptx",
        "resume-claude",
        "resume-codex",
        "resume-cursor",
        "review",
        "skill-design-principles",
        "statusline",
        "threejs-frame-conventions",
    };

    skills_manager manager;
    const int count = manager.discover({bundled});
    assert(count == static_cast<int>(expected.size()));
    std::set<std::string> names;
    for (const auto & skill : manager.get_skills()) {
        names.insert(skill.name);
        assert(!skill.description.empty());
        assert(skill.description.size() <= 1024);
        assert(!skill.scripts.empty());
        assert(skill.name != "imagine");
    }
    assert(names == expected);

    printf("  PASS: bundled_skills_parse_when_present (%d)\n", count);
}

static void write_file(const fs::path & path, const std::string & content) {
    fs::create_directories(path.parent_path());
    std::ofstream file(path);
    assert(file.good());
    file << content;
}

static void test_discover_resources_respects_enable_flags() {
    const fs::path root = fs::temp_directory_path() / "llama-agent-resources-test";
    fs::remove_all(root);

    write_file(root / "AGENTS.md", "project instructions\n");
    write_file(root / ".llama-agent" / "skills" / "test-skill" / "SKILL.md",
               "---\n"
               "name: test-skill\n"
               "description: Test skill\n"
               "---\n"
               "Body\n");

    agent_resource_config enabled;
    enabled.working_dir = root.string();
    enabled.enable_skills = true;
    enabled.enable_agents_md = true;
    agent_resource_discovery discovered = agent_discover_resources(enabled);
    // Shipped skills next to this binary are discovered too. The project skill must be among them.
    assert(discovered.skills_count >= 1);
    bool found_project_skill = false;
    for (const auto & skill : discovered.skills.get_skills()) {
        if (skill.name == "test-skill") {
            found_project_skill = true;
        }
    }
    assert(found_project_skill);
    assert(discovered.agents_md_count == 1);
    assert(!discovered.skills_prompt_section().empty());
    assert(!discovered.agents_md_prompt_section().empty());

    agent_resource_config disabled = enabled;
    disabled.enable_skills = false;
    disabled.enable_agents_md = false;
    agent_resource_discovery skipped = agent_discover_resources(disabled);
    assert(skipped.skills_count == 0);
    assert(skipped.agents_md_count == 0);
    assert(skipped.skills_prompt_section().empty());
    assert(skipped.agents_md_prompt_section().empty());

    fs::remove_all(root);

    printf("  PASS: discover_resources_respects_enable_flags\n");
}

int main() {
    printf("Running agent resource tests...\n");
    test_skill_search_path_order();
    test_empty_working_dir_defaults_to_current_dir();
    test_executable_skills_directory_is_before_extras();
    test_discover_resources_respects_enable_flags();
    test_bundled_skills_parse_when_present();
    printf("\nAll agent resource tests passed!\n");
    return 0;
}
