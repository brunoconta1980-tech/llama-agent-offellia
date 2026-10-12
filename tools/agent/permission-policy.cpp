#include "permission.h"

#include <filesystem>

namespace fs = std::filesystem;

permission_policy::permission_policy() {
    // Writes, edits, shell, and paths outside the working directory are allowed
    // so the agent can create skills and AGENTS.md without a permission prompt.
    defaults_[permission_type::BASH]         = permission_state::ALLOW;
    defaults_[permission_type::FILE_READ]    = permission_state::ALLOW;
    defaults_[permission_type::FILE_WRITE]   = permission_state::ALLOW;
    defaults_[permission_type::FILE_EDIT]    = permission_state::ALLOW;
    defaults_[permission_type::GLOB]         = permission_state::ALLOW;
    defaults_[permission_type::EXTERNAL_DIR] = permission_state::ALLOW;

    dangerous_patterns_ = {
        "rm -rf", "rm -r /", "rm -f", "rmdir",
        "sudo ", "su -", "doas ",
        "chmod 777", "chmod -R", "chown -R",
        "curl | sh", "curl | bash", "wget | sh", "wget | bash",
        "curl -s | sh", "wget -O - |",
        "> /dev/", "dd if=", "mkfs.", ":(){:|:&};:",
        "pip install", "pip3 install", "npm i -g", "npm install -g",
        "brew install", "apt install", "apt-get install", "yum install",
        "git push -f", "git push --force", "git reset --hard",
        "kill -9", "killall", "pkill"
    };
}

void permission_policy::set_project_root(const std::string & path) {
    project_root_ = fs::absolute(path).string();
}

permission_state permission_policy::classify(
        const permission_request & request,
        bool yolo_mode,
        const std::map<std::string, permission_state> & session_overrides) const {
    if (yolo_mode) {
        return permission_state::ALLOW;
    }

    const std::string key = permission_override_key(request.tool_name, request.details);
    auto it = session_overrides.find(key);
    if (it != session_overrides.end()) {
        return it->second;
    }

    auto def_it = defaults_.find(request.type);
    if (def_it != defaults_.end()) {
        return def_it->second;
    }

    return permission_state::ALLOW;
}

bool permission_policy::is_external_path(const std::string & path) const {
    return !is_path_in_project(path);
}

bool permission_policy::is_dangerous_bash_command(const std::string & cmd) const {
    // Substring match so dangerous fragments embedded in compound commands
    // (e.g. "cd build && rm -rf /") are still flagged.
    return contains_pattern(cmd, dangerous_patterns_);
}

bool permission_policy::contains_pattern(const std::string & cmd, const std::vector<std::string> & patterns) {
    for (const auto & pattern : patterns) {
        if (cmd.find(pattern) != std::string::npos) {
            return true;
        }
    }
    return false;
}

bool permission_policy::is_path_in_project(const std::string & path) const {
    if (project_root_.empty()) {
        return true;
    }

    try {
        const std::string abs_path = fs::absolute(path).string();
        if (abs_path == project_root_) {
            return true;
        }

        std::string prefix = project_root_;
        if (prefix.back() != '/' && prefix.back() != '\\') {
            prefix += '/';
        }
        return abs_path.find(prefix) == 0;
    } catch (...) {
        return false;
    }
}
