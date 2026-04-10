// SPDX-License-Identifier: LGPL-2.1-or-later

/***************************************************************************
 *   Copyright (c) 2025 Werner Mayer <wmayer[at]users.sourceforge.net>     *
 *                                                                         *
 *   This file is part of FreeCAD.                                         *
 *                                                                         *
 *   FreeCAD is free software: you can redistribute it and/or modify it    *
 *   under the terms of the GNU Lesser General Public License as           *
 *   published by the Free Software Foundation, either version 2.1 of the  *
 *   License, or (at your option) any later version.                       *
 *                                                                         *
 *   FreeCAD is distributed in the hope that it will be useful, but        *
 *   WITHOUT ANY WARRANTY; without even the implied warranty of            *
 *   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU      *
 *   Lesser General Public License for more details.                       *
 *                                                                         *
 *   You should have received a copy of the GNU Lesser General Public      *
 *   License along with FreeCAD. If not, see                               *
 *   <https://www.gnu.org/licenses/>.                                      *
 *                                                                         *
 **************************************************************************/

#include <array>
#include <clocale>
#include <filesystem>
#include <boost/version.hpp>
#include <boost/tokenizer.hpp>
#include <QDir>
#include <QFileInfo>
#include <QLocale>
#include <QProcessEnvironment>
#include <QRegularExpression>
#include <QRegularExpressionMatch>
#include <QSettings>
#include <unicode/locid.h>

#include <LibraryVersions.h>

#include <Base/Console.h>
#include <Base/Exception.h>
#include <Base/Interpreter.h>
#include <Base/Tools.h>

#include "Application.h"
#include "Metadata.h"
#include "ProgramInformation.h"

#ifdef FC_OS_WIN32
#include <windows.h>
#endif

using namespace App;
namespace fs = std::filesystem;

namespace {

std::ostream& operator<<(std::ostream& os, const QString& str)
{
    os << str.toStdString();
    return os;
}

QString territoryToString(const QLocale& locale)
{
#if QT_VERSION < QT_VERSION_CHECK(6, 6, 0)
    return QLocale::countryToString(locale.country());
#else
    return QLocale::territoryToString(locale.territory());
#endif
}

QString describeSeparator(const QString& separator)
{
    if (separator.isEmpty()) {
        return QStringLiteral("<empty>");
    }

    QString value = separator;
    if (separator == QStringLiteral(" ")) {
        value = QStringLiteral("<space>");
    }
    else if (separator == QString(QChar(0x00A0))) {
        value = QStringLiteral("<nbsp>");
    }
    else if (separator == QString(QChar(0x202F))) {
        value = QStringLiteral("<nnbsp>");
    }

    QString codepoints;
    for (const auto ch : separator) {
        if (!codepoints.isEmpty()) {
            codepoints += QLatin1Char(' ');
        }
        codepoints += QStringLiteral("U+%1")
                          .arg(static_cast<uint>(ch.unicode()), 4, 16, QLatin1Char('0'))
                          .toUpper();
    }

    return QStringLiteral("%1 (%2)").arg(value, codepoints);
}

QString formatQtLocale(const QLocale& locale)
{
    return QStringLiteral("%1/%2 (name=%3, bcp47=%4, decimal=%5, group=%6)")
        .arg(QLocale::languageToString(locale.language()),
             territoryToString(locale),
             locale.name(),
             locale.bcp47Name(),
             describeSeparator(locale.decimalPoint()),
             describeSeparator(locale.groupSeparator()));
}

QString getCLocaleName(const int category)
{
    if (const char* localeName = setlocale(category, nullptr)) {
        return QString::fromLocal8Bit(localeName);
    }

    return QStringLiteral("<null>");
}

QString getEnvValue(const QProcessEnvironment& env, const QString& name)
{
    return env.contains(name) ? env.value(name) : QStringLiteral("<unset>");
}

QString getIcuDefaultLocale()
{
    const auto locale = icu::Locale::getDefault();
    return QString::fromLatin1(locale.getName());
}

#ifdef FC_OS_WIN32
QString getWindowsLocaleName(int (WINAPI* localeFn)(LPWSTR, int))
{
    std::array<wchar_t, LOCALE_NAME_MAX_LENGTH> buffer {};
    const int written = localeFn(buffer.data(), static_cast<int>(buffer.size()));
    if (written <= 0) {
        return QStringLiteral("<unavailable>");
    }

    return QString::fromWCharArray(buffer.data());
}

QString getWindowsLocaleName(const LCID localeId)
{
    std::array<wchar_t, LOCALE_NAME_MAX_LENGTH> buffer {};
    const int written = LCIDToLocaleName(localeId, buffer.data(), static_cast<int>(buffer.size()), 0);
    if (written <= 0) {
        return QStringLiteral("<unavailable>");
    }

    return QString::fromWCharArray(buffer.data());
}

QString getWindowsLocaleNameFromLangId(const LANGID languageId)
{
    return getWindowsLocaleName(MAKELCID(languageId, SORT_DEFAULT));
}

QString getWindowsLocaleInfo(PCWSTR localeName, const LCTYPE localeType)
{
    std::array<wchar_t, 32> buffer {};
    const int written
        = GetLocaleInfoEx(localeName, localeType, buffer.data(), static_cast<int>(buffer.size()));
    if (written <= 0) {
        return QStringLiteral("<unavailable>");
    }

    return QString::fromWCharArray(buffer.data());
}
#endif

}

std::string ProgramInformation::prettyProductInfoWrapper()
{
    auto productName = QSysInfo::prettyProductName();
#ifdef FC_OS_MACOSX
    auto macosVersionFile = QStringLiteral(
        "/System/Library/CoreServices/.SystemVersionPlatform.plist"
    );
    auto fi = QFileInfo(macosVersionFile);
    if (fi.exists() && fi.isReadable()) {
        auto plistFile = QFile(macosVersionFile);
        plistFile.open(QIODevice::ReadOnly);
        while (!plistFile.atEnd()) {
            auto line = plistFile.readLine();
            if (line.contains("ProductUserVisibleVersion")) {
                auto nextLine = plistFile.readLine();
                if (nextLine.contains("<string>")) {
                    QRegularExpression re(QStringLiteral("\\s*<string>(.*)</string>"));
                    auto matches = re.match(QString::fromUtf8(nextLine));
                    if (matches.hasMatch()) {
                        productName = QStringLiteral("macOS ") + matches.captured(1);
                        break;
                    }
                }
            }
        }
    }
#endif
#ifdef FC_OS_WIN64
    QSettings regKey {
        QStringLiteral("HKEY_LOCAL_MACHINE\\SOFTWARE\\Microsoft\\Windows NT\\CurrentVersion"),
        QSettings::NativeFormat
    };
    if (regKey.contains(QStringLiteral("CurrentBuildNumber"))) {
        auto buildNumber = regKey.value(QStringLiteral("CurrentBuildNumber")).toInt();
        if (buildNumber > 0) {
            if (buildNumber < 9200) {
                productName = QStringLiteral("Windows 7 build %1").arg(buildNumber);
            }
            else if (buildNumber < 10240) {
                productName = QStringLiteral("Windows 8 build %1").arg(buildNumber);
            }
            else if (buildNumber < 22000) {
                productName = QStringLiteral("Windows 10 build %1").arg(buildNumber);
            }
            else {
                productName = QStringLiteral("Windows 11 build %1").arg(buildNumber);
            }
        }
    }
#endif
    return productName.toStdString();
}

void ProgramInformation::addModuleInfo(std::stringstream& str, const std::string& path)
{
    QString modPath = QString::fromStdString(path);
    QFileInfo mod(modPath);
    if (mod.isHidden()) {  // Ignore hidden directories
        return;
    }
    std::string addonName = mod.isDir() ? QDir(modPath).dirName().toStdString()
                                        : mod.fileName().toStdString();
    std::string versionString;
    try {
        auto metadataFile = std::filesystem::path(mod.absoluteFilePath().toStdString())
            / "package.xml";
        if (std::filesystem::exists(metadataFile)) {
            App::Metadata metadata(metadataFile);
            if (!metadata.name().empty()) {
                addonName = metadata.name();
            }
            if (metadata.version() != App::Meta::Version()) {
                versionString = " " + metadata.version().str();
            }
        }
    }
    catch (const Base::Exception& e) {
        auto what = QString::fromUtf8(e.what()).trimmed().replace(
            QChar::fromLatin1('\n'),
            QChar::fromLatin1(' ')
        );
        str << " (Malformed metadata: " << what << ")";
    }
    str << "  * " << addonName << versionString;
    QFileInfo disablingFile(mod.absoluteFilePath(), QStringLiteral("ADDON_DISABLED"));
    if (disablingFile.exists()) {
        str << " (Disabled)";
    }

    str << "\n";
}

std::string ProgramInformation::getValueOrEmpty(
    const std::map<std::string, std::string>& map,
    const std::string& key)
{
    auto it = map.find(key);
    return (it != map.end()) ? it->second : std::string();
}

void ProgramInformation::getVerboseCommonInfo(
    std::stringstream& str,
    const std::map<std::string, std::string>& mConfig)
{
    getSystemInformation(str);
    getVersionInformation(mConfig, str);
    getPackageInformation(str);
    getBuildInformation(mConfig, str);
    getLibraryVersions(str);
    getLocale(str);
}

void ProgramInformation::getSystemInformation(std::stringstream& str)
{
    auto sysenv = QProcessEnvironment::systemEnvironment();
    const QString deskEnv = sysenv.value(QStringLiteral("XDG_CURRENT_DESKTOP"));
    const QString deskSess = sysenv.value(QStringLiteral("DESKTOP_SESSION"));

    QStringList deskInfoList;
    QString deskInfo;

    if (!deskEnv.isEmpty()) {
        deskInfoList.append(deskEnv);
    }
    if (!deskSess.isEmpty()) {
        deskInfoList.append(deskSess);
    }

    const QString sysType = QSysInfo::productType();
    if (sysType != QLatin1String("windows") && sysType != QLatin1String("macos")) {
        QString sessionType = sysenv.value(QStringLiteral("XDG_SESSION_TYPE"));
        if (sessionType == QLatin1String("x11")) {
            sessionType = QStringLiteral("xcb");
        }
        deskInfoList.append(sessionType);
    }
    if (!deskInfoList.isEmpty()) {
        deskInfo = QLatin1String(" (") + deskInfoList.join(QLatin1String("/")) + QLatin1String(")");
    }

    str << "OS: " << prettyProductInfoWrapper() << deskInfo << '\n';
    if (QSysInfo::buildCpuArchitecture() == QSysInfo::currentCpuArchitecture()) {
        str << "Architecture: " << QSysInfo::buildCpuArchitecture() << "\n";
    }
    else {
        str << "Architecture: " << QSysInfo::buildCpuArchitecture()
            << "(running on: " << QSysInfo::currentCpuArchitecture() << ")\n";
    }
}

void ProgramInformation::getPackageInformation(std::stringstream& str)
{
#ifdef FC_CONDA
    str << " Conda";
#endif
#ifdef FC_FLATPAK
    str << " Flatpak";
#endif
    auto sysenv = QProcessEnvironment::systemEnvironment();
    const QString appimage = sysenv.value(QStringLiteral("APPIMAGE"));
    if (!appimage.isEmpty()) {
        str << " AppImage";
    }
    const QString snap = sysenv.value(QStringLiteral("SNAP_REVISION"));
    if (!snap.isEmpty()) {
        str << " Snap " << snap;
    }
    str << '\n';
}

void ProgramInformation::getVersionInformation(
    const std::map<std::string, std::string>& mConfig,
    std::stringstream& str)
{
    const auto major = getValueOrEmpty(mConfig, "BuildVersionMajor");
    const auto minor = getValueOrEmpty(mConfig, "BuildVersionMinor");
    const auto point = getValueOrEmpty(mConfig, "BuildVersionPoint");
    const auto suffix = getValueOrEmpty(mConfig, "BuildVersionSuffix");
    const auto build = getValueOrEmpty(mConfig, "BuildRevision");
    str << "Version: " << major << "." << minor << "." << point << suffix << "." << build;
}

void ProgramInformation::getBuildInformation(
    const std::map<std::string, std::string>& mConfig,
    std::stringstream& str)
{
    const auto buildDate = getValueOrEmpty(mConfig, "BuildRevisionDate");
    str << "Build date: " << buildDate << "\n";

#if defined(_DEBUG) || defined(DEBUG)
    str << "Build type: Debug\n";
#elif defined(NDEBUG)
    str << "Build type: Release\n";
#elif defined(CMAKE_BUILD_TYPE)
    str << "Build type: " << CMAKE_BUILD_TYPE << '\n';
#else
    str << "Build type: Unknown\n";
#endif
    const auto buildRevisionBranch = getValueOrEmpty(mConfig, "BuildRevisionBranch");
    if (!buildRevisionBranch.empty()) {
        str << "Branch: " << buildRevisionBranch << '\n';
    }
    const auto buildRevisionHash = getValueOrEmpty(mConfig, "BuildRevisionHash");
    if (!buildRevisionHash.empty()) {
        str << "Hash: " << buildRevisionHash << '\n';
    }
}

void ProgramInformation::getLibraryVersions(std::stringstream& str)
{
    // report also the version numbers of the most important libraries in FreeCAD
    str << "Python " << PY_VERSION << ", ";
    str << "Qt " << QT_VERSION_STR << ", ";
    str << "Coin " << fcCoin3dVersion << ", ";
    str << "Vtk " << fcVtkVersion << ", ";
    str << "boost " << BOOST_LIB_VERSION << ", ";
    str << "Eigen3 " << fcEigen3Version << ", ";
    str << "PySide " << fcPysideVersion << '\n';
    str << "shiboken " << fcShibokenVersion << ", ";
#ifdef SMESH_VERSION_STR
    str << "SMESH " << SMESH_VERSION_STR << ", ";
#endif
    str << "xerces-c " << fcXercescVersion << ", ";
    getIfcInfo(str);
#if defined(OCC_VERSION_STRING_EXT)
    str << "OCC " << OCC_VERSION_STRING_EXT << '\n';
#endif
}

void ProgramInformation::getIfcInfo(std::stringstream& str)
{
    try {
        Base::PyGILStateLocker lock;
        Py::Module module(PyImport_ImportModule("ifcopenshell"), true);
        if (!module.isNull() && module.hasAttr("version")) {
            Py::String version(module.getAttr("version"));
            auto ver_str = static_cast<std::string>(version);
            str << "IfcOpenShell " << ver_str << ", ";
        }
        else {
            Base::Console().log("Module 'ifcopenshell' not found (safe to ignore, unless using "
                                "the BIM workbench and IFC).\n");
        }
    }
    catch (const Py::Exception&) {
        Base::PyGILStateLocker lock;
        Base::PyException e;
        Base::Console().log("%s\n", e.what());
    }
}

void ProgramInformation::getLocale(std::stringstream& str)
{
    const QLocale currentLocale;
    const QLocale systemLocale = QLocale::system();

    str << "Locale: " << QLocale::languageToString(currentLocale.language()) << "/"
        << territoryToString(currentLocale) << " (" << currentLocale.name() << ")";
    if (currentLocale != systemLocale) {
        str << " [ OS: " << QLocale::languageToString(systemLocale.language()) << "/"
            << territoryToString(systemLocale) << " (" << systemLocale.name() << ") ]";
    }
    str << "\n";

    const auto processEnv = QProcessEnvironment::systemEnvironment();

    str << "Locale diagnostics:\n";
    str << "  Qt current/default locale: " << formatQtLocale(currentLocale) << '\n';
    str << "  Qt system locale: " << formatQtLocale(systemLocale) << '\n';
    str << "  ICU default locale: " << getIcuDefaultLocale() << '\n';
    str << "  Stored OS numeric locale: "
        << QString::fromStdString(Base::Tools::getOperatingSystemNumericLocale()) << '\n';
    str << "  C locale LC_ALL: " << getCLocaleName(LC_ALL) << '\n';
    str << "  C locale LC_CTYPE: " << getCLocaleName(LC_CTYPE) << '\n';
    str << "  C locale LC_NUMERIC: " << getCLocaleName(LC_NUMERIC) << '\n';
    str << "  C locale LC_TIME: " << getCLocaleName(LC_TIME) << '\n';
    str << "  C locale LC_MONETARY: " << getCLocaleName(LC_MONETARY) << '\n';

    for (const auto& envName : std::array {
             QStringLiteral("LANG"),
             QStringLiteral("LANGUAGE"),
             QStringLiteral("LC_ALL"),
             QStringLiteral("LC_CTYPE"),
             QStringLiteral("LC_NUMERIC"),
             QStringLiteral("LC_TIME"),
             QStringLiteral("MSYSTEM"),
             QStringLiteral("MSYSTEM_PREFIX"),
             QStringLiteral("MSYS2_PATH_TYPE"),
             QStringLiteral("MINGW_PREFIX"),
             QStringLiteral("PYTHONHOME"),
             QStringLiteral("FC_PYTHONHOME"),
         }) {
        str << "  Env " << envName << ": " << getEnvValue(processEnv, envName) << '\n';
    }

#ifdef FC_OS_WIN32
    str << "  Win user default locale: " << getWindowsLocaleName(GetUserDefaultLocaleName) << '\n';
    str << "  Win system default locale: " << getWindowsLocaleName(GetSystemDefaultLocaleName)
        << '\n';
    str << "  Win thread locale: " << getWindowsLocaleName(GetThreadLocale()) << '\n';
    str << "  Win user decimal separator: "
        << getWindowsLocaleInfo(LOCALE_NAME_USER_DEFAULT, LOCALE_SDECIMAL) << '\n';
    str << "  Win user group separator: "
        << getWindowsLocaleInfo(LOCALE_NAME_USER_DEFAULT, LOCALE_STHOUSAND) << '\n';
    str << "  Win system decimal separator: "
        << getWindowsLocaleInfo(LOCALE_NAME_SYSTEM_DEFAULT, LOCALE_SDECIMAL) << '\n';
    str << "  Win system group separator: "
        << getWindowsLocaleInfo(LOCALE_NAME_SYSTEM_DEFAULT, LOCALE_STHOUSAND) << '\n';
    str << "  Win user UI language: "
        << getWindowsLocaleNameFromLangId(GetUserDefaultUILanguage()) << '\n';
    str << "  Win system UI language: "
        << getWindowsLocaleNameFromLangId(GetSystemDefaultUILanguage()) << '\n';
    str << "  Win thread UI language: "
        << getWindowsLocaleNameFromLangId(GetThreadUILanguage()) << '\n';
#endif
}

void ProgramInformation::getVerboseAddOnsInfo(
    std::stringstream& str,
    const std::map<std::string, std::string>& mConfig)
{
    // Add installed module information:
    const auto modDir = fs::path(Application::getUserAppDataDir()) / "Mod";
    std::stringstream tmp;
    if (fs::exists(modDir) && fs::is_directory(modDir)) {
        for (const auto& mod : fs::directory_iterator(modDir)) {
            if (!fs::is_directory(mod)) {
                continue;  // Ignore files, only show directories
            }
            auto dirName = mod.path().string();
            addModuleInfo(tmp, dirName);
        }
    }
    const auto additionalModules = getValueOrEmpty(mConfig, "AdditionalModulePaths");

    if (!additionalModules.empty()) {
        boost::char_separator<char> sep(";");
        boost::tokenizer<boost::char_separator<char>> mods(additionalModules, sep);
        for (const auto& mod : mods) {
            addModuleInfo(tmp, mod);
        }
    }

    std::string addons = tmp.str();
    if (!addons.empty()) {
        str << "Installed mods:\n";
        str << addons;
    }
}
