// SPDX-License-Identifier: LGPL-2.1-or-later

#ifndef APP_COMMANDLINE_H
#define APP_COMMANDLINE_H

#include <string>
#include <string_view>
#include <unordered_map>
#include <unordered_set>
#include <vector>

namespace App
{

class CommandLineOptions
{
public:
    bool has(std::string_view name) const;
    std::string valueOr(std::string_view name, std::string fallback = {}) const;
    const std::vector<std::string>& values(std::string_view name) const;

    void setFlag(std::string name);
    void setValue(std::string name, std::string value);
    void appendValue(std::string name, std::string value);

    void appendPositional(std::string value);
    const std::vector<std::string>& positional() const;

private:
    std::unordered_set<std::string> flags;
    std::unordered_map<std::string, std::vector<std::string>> options;
    std::vector<std::string> positionalArgs;
};

CommandLineOptions parseCommandLine(int argc, char** argv, const std::string& exeName);

std::string commandLineHelp(const std::string& exeName);

}  // namespace App

#endif  // APP_COMMANDLINE_H
