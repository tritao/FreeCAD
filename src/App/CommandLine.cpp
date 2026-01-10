// SPDX-License-Identifier: LGPL-2.1-or-later
// SPDX-FileCopyrightText: 2026 The FreeCAD project association AISBL
// SPDX-FileNotice: Part of the FreeCAD project.
/******************************************************************************
 *                                                                            *
 *   FreeCAD is free software: you can redistribute it and/or modify          *
 *   it under the terms of the GNU Lesser General Public License as           *
 *   published by the Free Software Foundation, either version 2.1            *
 *   of the License, or (at your option) any later version.                   *
 *                                                                            *
 *   FreeCAD is distributed in the hope that it will be useful,               *
 *   but WITHOUT ANY WARRANTY; without even the implied warranty              *
 *   of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.                  *
 *   See the GNU Lesser General Public License for more details.              *
 *                                                                            *
 *   You should have received a copy of the GNU Lesser General Public         *
 *   License along with FreeCAD. If not, see https://www.gnu.org/licenses     *
 *                                                                            *
 ******************************************************************************/

#include "CommandLine.h"

#include <algorithm>
#include <cctype>
#include <filesystem>
#include <fstream>
#include <optional>
#include <sstream>

#include <Base/Console.h>
#include <Base/Exception.h>

#include "ProgramOptionsUtilities.h"

namespace
{

struct OptionSpec
{
    enum class Kind
    {
        Flag,
        SingleValue,
        MultiValue,
        MultiToken,
        ImplicitEmptyValue,
    };

    const char* longName;
    char shortName;
    Kind kind;
    bool allowInConfigFile;
};

constexpr OptionSpec kSpecs[] = {
    // generic (command line only)
    {"help", 'h', OptionSpec::Kind::Flag, false},
    {"version", 'v', OptionSpec::Kind::Flag, false},
    {"verbose", 0, OptionSpec::Kind::Flag, false},
    {"console", 'c', OptionSpec::Kind::Flag, false},
    {"dump-config", 0, OptionSpec::Kind::Flag, false},
    {"get-config", 0, OptionSpec::Kind::SingleValue, false},
    {"set-config", 0, OptionSpec::Kind::MultiToken, false},
    {"keep-deprecated-paths", 0, OptionSpec::Kind::Flag, false},
    {"response-file", 0, OptionSpec::Kind::SingleValue, false},

    // config + hidden (command line and config file)
    {"write-log", 'l', OptionSpec::Kind::Flag, true},
    {"log-file", 0, OptionSpec::Kind::SingleValue, true},
    {"user-cfg", 'u', OptionSpec::Kind::SingleValue, true},
    {"system-cfg", 's', OptionSpec::Kind::SingleValue, true},
    {"run-test", 't', OptionSpec::Kind::ImplicitEmptyValue, true},
    {"run-open", 'r', OptionSpec::Kind::ImplicitEmptyValue, true},
    {"module-path", 'M', OptionSpec::Kind::MultiValue, true},
    {"macro-path", 'E', OptionSpec::Kind::MultiValue, true},
    {"python-path", 'P', OptionSpec::Kind::MultiValue, true},
    {"disable-addon", 0, OptionSpec::Kind::MultiValue, true},
    {"single-instance", 0, OptionSpec::Kind::Flag, true},
    {"safe-mode", 0, OptionSpec::Kind::Flag, true},
    {"pass", 0, OptionSpec::Kind::MultiToken, true},

    {"input-file", 0, OptionSpec::Kind::MultiValue, true},
    {"output", 0, OptionSpec::Kind::SingleValue, true},
    {"hidden", 0, OptionSpec::Kind::Flag, true},

    // GUI/window system args (accepted and ignored; also allowed in FreeCAD.cfg)
    {"style", 0, OptionSpec::Kind::SingleValue, true},
    {"stylesheet", 0, OptionSpec::Kind::SingleValue, true},
    {"session", 0, OptionSpec::Kind::SingleValue, true},
    {"reverse", 0, OptionSpec::Kind::Flag, true},
    {"widgetcount", 0, OptionSpec::Kind::Flag, true},
    {"graphicssystem", 0, OptionSpec::Kind::SingleValue, true},
    {"display", 0, OptionSpec::Kind::SingleValue, true},
    {"geometry", 0, OptionSpec::Kind::SingleValue, true},
    {"font", 0, OptionSpec::Kind::SingleValue, true},
    {"fn", 0, OptionSpec::Kind::SingleValue, true},
    {"background", 0, OptionSpec::Kind::SingleValue, true},
    {"bg", 0, OptionSpec::Kind::SingleValue, true},
    {"foreground", 0, OptionSpec::Kind::SingleValue, true},
    {"fg", 0, OptionSpec::Kind::SingleValue, true},
    {"button", 0, OptionSpec::Kind::SingleValue, true},
    {"btn", 0, OptionSpec::Kind::SingleValue, true},
    {"name", 0, OptionSpec::Kind::SingleValue, true},
    {"title", 0, OptionSpec::Kind::SingleValue, true},
    {"visual", 0, OptionSpec::Kind::SingleValue, true},
    {"ncols", 0, OptionSpec::Kind::SingleValue, true},
    {"cmap", 0, OptionSpec::Kind::Flag, true},
#if defined(FC_OS_MACOSX)
    {"psn", 0, OptionSpec::Kind::SingleValue, true},
#endif
};

const OptionSpec* findSpecByLong(std::string_view name)
{
    for (const auto& s : kSpecs) {
        if (name == s.longName) {
            return &s;
        }
    }
    return nullptr;
}

const OptionSpec* findSpecByShort(char c)
{
    for (const auto& s : kSpecs) {
        if (s.shortName == c) {
            return &s;
        }
    }
    return nullptr;
}

bool isOptionToken(std::string_view token)
{
    return token.size() >= 2 && token[0] == '-';
}

std::vector<std::string> splitWhitespace(const std::string& text)
{
    std::vector<std::string> out;
    std::string cur;
    for (char ch : text) {
        if (std::isspace(static_cast<unsigned char>(ch))) {
            if (!cur.empty()) {
                out.push_back(std::move(cur));
                cur.clear();
            }
            continue;
        }
        cur.push_back(ch);
    }
    if (!cur.empty()) {
        out.push_back(std::move(cur));
    }
    return out;
}

std::vector<std::string> loadResponseFile(const std::string& path)
{
    std::ifstream ifs(path);
    if (!ifs) {
        Base::Console().error("Could not open the response file\n");
        std::stringstream str;
        str << "Could not open the response file: '" << path << "'" << '\n';
        throw Base::UnknownProgramOption(str.str());
    }
    std::stringstream ss;
    ss << ifs.rdbuf();
    return splitWhitespace(ss.str());
}

struct Token
{
    std::string name;
    std::optional<std::string> value;
    bool isLongOrDashLong = false;
    bool isShort = false;
};

Token parseOptionToken(const std::string& raw)
{
    if (raw.size() < 2 || raw[0] != '-') {
        return {};
    }

    // Support FreeCAD's customSyntax conventions (-display, @file).
    if (auto kv = App::Util::customSyntax(raw); !kv.first.empty()) {
        Token t;
        t.name = kv.first;
        t.value = kv.second;
        t.isLongOrDashLong = true;
        return t;
    }

    Token t;
    if (raw.rfind("--", 0) == 0) {
        t.isLongOrDashLong = true;
        const auto eq = raw.find('=');
        if (eq != std::string::npos) {
            t.name = raw.substr(2, eq - 2);
            t.value = raw.substr(eq + 1);
        }
        else {
            t.name = raw.substr(2);
        }
        return t;
    }

    if (raw.size() == 2) {
        t.isShort = true;
        t.name = raw.substr(1);
        return t;
    }

    // Accept single-dash long options (-style, -display, etc.)
    t.isLongOrDashLong = true;
    const auto eq = raw.find('=');
    if (eq != std::string::npos) {
        t.name = raw.substr(1, eq - 1);
        t.value = raw.substr(eq + 1);
    }
    else {
        t.name = raw.substr(1);
    }
    return t;
}

bool tokenLooksLikeKnownOption(const std::string& token)
{
    if (!isOptionToken(token)) {
        return false;
    }
    const Token t = parseOptionToken(token);
    if (t.isShort && t.name.size() == 1) {
        return findSpecByShort(t.name[0]) != nullptr;
    }
    if (!t.name.empty()) {
        return findSpecByLong(t.name) != nullptr;
    }
    return false;
}

void applyOption(App::CommandLineOptions& out,
                 const OptionSpec& spec,
                 const std::optional<std::string>& directValue,
                 const std::optional<std::string>& followingValue)
{
    switch (spec.kind) {
        case OptionSpec::Kind::Flag:
            out.setFlag(spec.longName);
            return;
        case OptionSpec::Kind::SingleValue: {
            if (directValue) {
                out.setValue(spec.longName, *directValue);
                return;
            }
            if (!followingValue) {
                std::stringstream msg;
                msg << "Missing value for option: " << spec.longName;
                throw Base::UnknownProgramOption(msg.str());
            }
            out.setValue(spec.longName, *followingValue);
            return;
        }
        case OptionSpec::Kind::MultiValue: {
            if (directValue) {
                out.appendValue(spec.longName, *directValue);
                return;
            }
            if (!followingValue) {
                std::stringstream msg;
                msg << "Missing value for option: " << spec.longName;
                throw Base::UnknownProgramOption(msg.str());
            }
            out.appendValue(spec.longName, *followingValue);
            return;
        }
        case OptionSpec::Kind::ImplicitEmptyValue: {
            if (directValue) {
                out.setValue(spec.longName, *directValue);
                return;
            }
            if (followingValue) {
                out.setValue(spec.longName, *followingValue);
                return;
            }
            out.setValue(spec.longName, "");
            return;
        }
        case OptionSpec::Kind::MultiToken:
            // handled by caller (consumes many tokens)
            return;
    }
}

void parseConfigFile(App::CommandLineOptions& out, const std::filesystem::path& cfgPath)
{
    std::ifstream in(cfgPath);
    if (!in) {
        return;
    }

    std::string line;
    while (std::getline(in, line)) {
        auto ltrim = [](std::string& s) {
            const auto it = std::find_if_not(s.begin(), s.end(), [](unsigned char c) { return std::isspace(c); });
            s.erase(s.begin(), it);
        };
        auto rtrim = [](std::string& s) {
            const auto it = std::find_if_not(s.rbegin(), s.rend(), [](unsigned char c) { return std::isspace(c); });
            s.erase(it.base(), s.end());
        };

        ltrim(line);
        rtrim(line);
        if (line.empty() || line[0] == '#' || line[0] == ';') {
            continue;
        }

        std::string key;
        std::string value;

        const auto eq = line.find('=');
        if (eq != std::string::npos) {
            key = line.substr(0, eq);
            value = line.substr(eq + 1);
        }
        else {
            std::istringstream str(line);
            str >> key;
            std::getline(str, value);
        }

        ltrim(key);
        rtrim(key);
        ltrim(value);
        rtrim(value);

        if (key.empty()) {
            continue;
        }

        const OptionSpec* spec = findSpecByLong(key);
        if (!spec || !spec->allowInConfigFile) {
            continue;
        }

        if (spec->kind == OptionSpec::Kind::Flag) {
            out.setFlag(spec->longName);
            continue;
        }
        if (spec->kind == OptionSpec::Kind::MultiValue) {
            if (!value.empty()) {
                out.appendValue(spec->longName, value);
            }
            continue;
        }
        if (!value.empty()) {
            out.setValue(spec->longName, value);
        }
    }
}

}  // namespace

namespace App
{

bool CommandLineOptions::has(std::string_view name) const
{
    if (flags.find(std::string(name)) != flags.end()) {
        return true;
    }
    return options.find(std::string(name)) != options.end();
}

std::string CommandLineOptions::valueOr(std::string_view name, std::string fallback) const
{
    const auto it = options.find(std::string(name));
    if (it == options.end() || it->second.empty()) {
        return fallback;
    }
    return it->second.back();
}

const std::vector<std::string>& CommandLineOptions::values(std::string_view name) const
{
    static const std::vector<std::string> empty;
    const auto it = options.find(std::string(name));
    if (it == options.end()) {
        return empty;
    }
    return it->second;
}

void CommandLineOptions::setFlag(std::string name)
{
    flags.insert(std::move(name));
}

void CommandLineOptions::setValue(std::string name, std::string value)
{
    auto& v = options[std::move(name)];
    v.clear();
    v.push_back(std::move(value));
}

void CommandLineOptions::appendValue(std::string name, std::string value)
{
    options[std::move(name)].push_back(std::move(value));
}

void CommandLineOptions::appendPositional(std::string value)
{
    positionalArgs.push_back(std::move(value));
    appendValue("input-file", positionalArgs.back());
}

const std::vector<std::string>& CommandLineOptions::positional() const
{
    return positionalArgs;
}

CommandLineOptions parseCommandLine(int argc, char** argv, const std::string& exeName)
{
    CommandLineOptions out;

    std::vector<std::string> args;
    args.reserve(static_cast<size_t>(argc > 1 ? argc - 1 : 0));
    for (int i = 1; i < argc; ++i) {
        args.emplace_back(argv[i] ? argv[i] : "");
    }

    bool endOfOptions = false;
    for (size_t i = 0; i < args.size(); ++i) {
        const std::string& raw = args[i];
        if (!endOfOptions && raw == "--") {
            endOfOptions = true;
            continue;
        }

        if (!raw.empty() && raw[0] == '@') {
            out.setValue("response-file", raw.substr(1));
            continue;
        }

        if (endOfOptions || !isOptionToken(raw)) {
            out.appendPositional(raw);
            continue;
        }

        const Token tok = parseOptionToken(raw);
        if (tok.isShort && tok.name.size() == 1) {
            const OptionSpec* spec = findSpecByShort(tok.name[0]);
            if (!spec) {
                std::stringstream msg;
                msg << "Unknown option: " << raw << '\n' << '\n' << commandLineHelp(exeName) << '\n';
                throw Base::UnknownProgramOption(msg.str());
            }

            std::optional<std::string> next;
            if (spec->kind != OptionSpec::Kind::Flag && !tok.value && (i + 1) < args.size()
                && !tokenLooksLikeKnownOption(args[i + 1])) {
                next = args[i + 1];
                ++i;
            }

            applyOption(out, *spec, tok.value, next);
            continue;
        }

        if (tok.name.empty()) {
            continue;
        }

        const OptionSpec* spec = findSpecByLong(tok.name);
        if (!spec) {
            std::stringstream msg;
            msg << "Unknown option: " << raw << '\n' << '\n' << commandLineHelp(exeName) << '\n';
            throw Base::UnknownProgramOption(msg.str());
        }

        if (std::string_view(spec->longName) == "response-file") {
            const std::string path = tok.value ? *tok.value : ((i + 1) < args.size() ? args[i + 1] : "");
            if (path.empty()) {
                throw Base::UnknownProgramOption("Missing value for option: response-file");
            }
            out.setValue("response-file", path);
            if (!tok.value) {
                ++i;
            }
            continue;
        }

        if (spec->kind == OptionSpec::Kind::MultiToken) {
            if (std::string_view(spec->longName) == "pass") {
                out.setFlag("pass");
                for (size_t j = i + 1; j < args.size(); ++j) {
                    out.appendValue("pass", args[j]);
                }
                break;
            }

            // Consume tokens until the next token looks like a known option.
            for (size_t j = i + 1; j < args.size(); ++j) {
                if (tokenLooksLikeKnownOption(args[j])) {
                    i = j - 1;
                    break;
                }
                out.appendValue(spec->longName, args[j]);
                i = j;
            }
            continue;
        }

        std::optional<std::string> next;
        if (spec->kind != OptionSpec::Kind::Flag && !tok.value && (i + 1) < args.size()
            && !tokenLooksLikeKnownOption(args[i + 1])) {
            next = args[i + 1];
            ++i;
        }

        applyOption(out, *spec, tok.value, next);
    }

    if (out.has("help")) {
        std::stringstream str;
        str << exeName << '\n' << '\n';
        str << "For a detailed description see https://www.freecad.org/wiki/Start_up_and_Configuration\n\n";
        str << "Usage: " << exeName << " [options] File1 File2 ...\n\n";
        str << commandLineHelp(exeName) << '\n';
        throw Base::ProgramInformation(str.str());
    }

    // Load FreeCAD.cfg (previous behavior: parsed after initial command line parse).
    parseConfigFile(out, std::filesystem::path("FreeCAD.cfg"));

    // If a response file was specified, parse it last (previous behavior: parsed after FreeCAD.cfg).
    if (out.has("response-file")) {
        const std::string path = out.valueOr("response-file");
        auto rf = loadResponseFile(path);
        // Treat response-file contents as command line tokens.
        std::vector<std::string> rfArgs;
        rfArgs.reserve(rf.size());
        for (auto& s : rf) {
            rfArgs.emplace_back(std::move(s));
        }
        bool rfEnd = false;
        for (size_t i = 0; i < rfArgs.size(); ++i) {
            const std::string& raw = rfArgs[i];
            if (!rfEnd && raw == "--") {
                rfEnd = true;
                continue;
            }
            if (rfEnd || raw.empty() || raw[0] == '@' || !isOptionToken(raw)) {
                out.appendPositional(raw);
                continue;
            }
            const Token tok = parseOptionToken(raw);
            if (tok.isShort && tok.name.size() == 1) {
                const OptionSpec* spec = findSpecByShort(tok.name[0]);
                if (!spec) {
                    continue;
                }
                std::optional<std::string> next;
                if (spec->kind != OptionSpec::Kind::Flag && !tok.value && (i + 1) < rfArgs.size()
                    && !tokenLooksLikeKnownOption(rfArgs[i + 1])) {
                    next = rfArgs[i + 1];
                    ++i;
                }
                applyOption(out, *spec, tok.value, next);
                continue;
            }
            if (tok.name.empty()) {
                continue;
            }
            const OptionSpec* spec = findSpecByLong(tok.name);
            if (!spec) {
                continue;
            }
            if (spec->kind == OptionSpec::Kind::MultiToken) {
                if (std::string_view(spec->longName) == "pass") {
                    out.setFlag("pass");
                    for (size_t j = i + 1; j < rfArgs.size(); ++j) {
                        out.appendValue("pass", rfArgs[j]);
                    }
                    break;
                }
                for (size_t j = i + 1; j < rfArgs.size(); ++j) {
                    if (tokenLooksLikeKnownOption(rfArgs[j])) {
                        i = j - 1;
                        break;
                    }
                    out.appendValue(spec->longName, rfArgs[j]);
                    i = j;
                }
                continue;
            }
            std::optional<std::string> next;
            if (spec->kind != OptionSpec::Kind::Flag && !tok.value && (i + 1) < rfArgs.size()
                && !tokenLooksLikeKnownOption(rfArgs[i + 1])) {
                next = rfArgs[i + 1];
                ++i;
            }
            applyOption(out, *spec, tok.value, next);
        }
    }

    return out;
}

std::string commandLineHelp(const std::string& /*exeName*/)
{
    // Keep this intentionally concise; FreeCAD's full CLI docs are on the wiki.
    return R"(Allowed options:
  -h, --help                 Prints help message
  -v, --version              Prints version string
      --verbose              Prints verbose version string
  -c, --console              Starts in console mode
  -l, --write-log            Writes FreeCAD.log to the user directory
      --log-file <path>      Log to an explicit file
  -u, --user-cfg <path>      User config file to load/save user settings
  -s, --system-cfg <path>    System config file to load/save system settings
  -t, --run-test[=<test>]    Run tests (0=all, empty=print list)
  -r, --run-open[=<test>]    Run tests and keep UI open
      --module-path <path>   Additional module paths (repeatable)
      --macro-path <path>    Additional macro paths (repeatable)
      --python-path <path>   Additional python paths (repeatable)
      --disable-addon <id>   Disable an addon (repeatable)
      --single-instance      Allow a single instance
      --safe-mode            Force safe mode
      --dump-config          Dumps configuration
      --get-config <key>     Prints the requested configuration key
      --set-config k=v ...   Sets one or more configuration keys
      --keep-deprecated-paths Keep config files on old location

Response files:
  @file or --response-file <file> expands whitespace-delimited arguments from file.)";
}

}  // namespace App
