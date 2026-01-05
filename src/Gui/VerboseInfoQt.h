// SPDX-License-Identifier: LGPL-2.1-or-later

#ifndef GUI_VERBOSE_INFO_QT_H
#define GUI_VERBOSE_INFO_QT_H

#include <cstdlib>
#include <filesystem>
#include <map>
#include <string>

#include <boost/version.hpp>

#include <QDir>
#include <QFile>
#include <QFileInfo>
#include <QLocale>
#include <QProcessEnvironment>
#include <QRegularExpression>
#include <QSettings>
#include <QSysInfo>
#include <QTextStream>

#include <App/Application.h>
#include <App/Metadata.h>
#include <Base/Console.h>
#include <Base/Interpreter.h>
#include <Base/Parameter.h>
#include <CXX/WrapPython.h>

#include <LibraryVersions.h>
#include <zlib.h>

namespace Gui::VerboseInfoQt
{

namespace fs = std::filesystem;

inline QString getValueOrEmpty(const std::map<std::string, std::string>& map, const std::string& key)
{
    auto it = map.find(key);
    return (it != map.end()) ? QString::fromStdString(it->second) : QString();
}

inline QString prettyProductInfoWrapper()
{
    auto productName = QSysInfo::prettyProductName();
#ifdef FC_OS_MACOSX
    auto macosVersionFile =
        QStringLiteral("/System/Library/CoreServices/.SystemVersionPlatform.plist");
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
        QSettings::NativeFormat};
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
    return productName;
}

inline void addModuleInfo(QTextStream& str, const QString& modPath, bool& firstMod)
{
    QFileInfo mod(modPath);
    if (mod.isHidden()) {  // Ignore hidden directories
        return;
    }
    if (firstMod) {
        firstMod = false;
        str << "Installed mods: \n";
    }
    str << "  * " << (mod.isDir() ? QDir(modPath).dirName() : mod.fileName());
    try {
        auto metadataFile = fs::path(mod.absoluteFilePath().toStdString()) / "package.xml";
        if (fs::exists(metadataFile)) {
            App::Metadata metadata(metadataFile);
            if (metadata.version() != App::Meta::Version()) {
                str << QLatin1String(" ") + QString::fromStdString(metadata.version().str());
            }
        }
    }
    catch (const Base::Exception& e) {
        auto what = QString::fromUtf8(e.what()).trimmed().replace(QChar::fromLatin1('\n'),
                                                                  QChar::fromLatin1(' '));
        str << " (Malformed metadata: " << what << ")";
    }
    QFileInfo disablingFile(mod.absoluteFilePath(), QStringLiteral("ADDON_DISABLED"));
    if (disablingFile.exists()) {
        str << " (Disabled)";
    }

    str << "\n";
}

inline void getVerboseCommonInfo(QTextStream& str, const std::map<std::string, std::string>& mConfig)
{
    const QString deskEnv =
        QProcessEnvironment::systemEnvironment().value(QStringLiteral("XDG_CURRENT_DESKTOP"),
                                                       QString());
    const QString deskSess =
        QProcessEnvironment::systemEnvironment().value(QStringLiteral("DESKTOP_SESSION"),
                                                       QString());

    const QString major = getValueOrEmpty(mConfig, "BuildVersionMajor");
    const QString minor = getValueOrEmpty(mConfig, "BuildVersionMinor");
    const QString point = getValueOrEmpty(mConfig, "BuildVersionPoint");
    const QString suffix = getValueOrEmpty(mConfig, "BuildVersionSuffix");
    const QString build = getValueOrEmpty(mConfig, "BuildRevision");
    const QString buildDate = getValueOrEmpty(mConfig, "BuildRevisionDate");

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
        QString sessionType =
            QProcessEnvironment::systemEnvironment().value(QStringLiteral("XDG_SESSION_TYPE"),
                                                          QString());
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
    str << "Version: " << major << "." << minor << "." << point << suffix << "." << build;

#ifdef FC_CONDA
    str << " Conda";
#endif
#ifdef FC_FLATPAK
    str << " Flatpak";
#endif
    const char* appimage = getenv("APPIMAGE");
    if (appimage) {
        str << " AppImage";
    }
    const char* snap = getenv("SNAP_REVISION");
    if (snap) {
        str << " Snap " << snap;
    }
    str << '\n';
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
    const QString buildRevisionBranch = getValueOrEmpty(mConfig, "BuildRevisionBranch");
    if (!buildRevisionBranch.isEmpty()) {
        str << "Branch: " << buildRevisionBranch << '\n';
    }
    const QString buildRevisionHash = getValueOrEmpty(mConfig, "BuildRevisionHash");
    if (!buildRevisionHash.isEmpty()) {
        str << "Hash: " << buildRevisionHash << '\n';
    }
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

    const char* cmd = "import ifcopenshell\n"
                      "version = ifcopenshell.version";
    PyObject* ifcopenshellVer = nullptr;

    try {
        ifcopenshellVer = Base::Interpreter().getValue(cmd, "version");
    }
    catch (const Base::Exception& e) {
        Base::Console().log(
            "%s (safe to ignore, unless using the BIM workbench and IFC).\n", e.what());
    }

    if (ifcopenshellVer) {
        const char* ifcopenshellVerAsStr = PyUnicode_AsUTF8(ifcopenshellVer);

        if (ifcopenshellVerAsStr) {
            str << "IfcOpenShell " << ifcopenshellVerAsStr << ", ";
        }
        Py_DECREF(ifcopenshellVer);
    }

#if defined(HAVE_OCC_VERSION)
    str << "OCC " << OCC_VERSION_MAJOR << "." << OCC_VERSION_MINOR << "." << OCC_VERSION_MAINTENANCE
#ifdef OCC_VERSION_DEVELOPMENT
        << "." OCC_VERSION_DEVELOPMENT
#endif
        << '\n';
#endif
    QLocale loc;
    str << "Locale: " << QLocale::languageToString(loc.language()) << "/"
#if QT_VERSION < QT_VERSION_CHECK(6, 6, 0)
        << QLocale::countryToString(loc.country())
#else
        << QLocale::territoryToString(loc.territory())
#endif
        << " (" << loc.name() << ")";
    if (loc != QLocale::system()) {
        loc = QLocale::system();
        str << " [ OS: " << QLocale::languageToString(loc.language()) << "/"
#if QT_VERSION < QT_VERSION_CHECK(6, 6, 0)
            << QLocale::countryToString(loc.country())
#else
            << QLocale::territoryToString(loc.territory())
#endif
            << " (" << loc.name() << ") ]";
    }
    str << "\n";

    ParameterGrp::handle hGrp =
        App::GetApplication().GetParameterGroupByPath("User parameter:BaseApp/Preferences/View");

    QString navStyle =
        QString::fromStdString(hGrp->GetASCII("NavigationStyle", "Gui::CADNavigationStyle"));
    // All navigation styles are named on the format "Gui::<Name>NavigationStyle"
    // so we remove the "Gui::" prefix and the "NavigationStyle" suffix before printing.
    navStyle.replace(QRegularExpression(QLatin1String("^Gui::")), {});
    navStyle.replace(QRegularExpression(QLatin1String("NavigationStyle$")), {});

    const QString orbitStyle =
        QStringLiteral("Turntable,Trackball,Free Turntable,Trackball Classic,Rounded Arcball")
            .split(QLatin1Char(','))
            .at(hGrp->GetInt("OrbitStyle", 4));
    const QString rotMode =
        QStringLiteral("Window center,Drag at cursor,Object center").split(QLatin1Char(',')).at(
            hGrp->GetInt("RotationMode", 0));

    str << QStringLiteral("Navigation Style/Orbit Style/Rotation Mode: %1/%2/%3\n")
               .arg(navStyle, orbitStyle, rotMode);
}

inline void getVerboseAddOnsInfo(QTextStream& str, const std::map<std::string, std::string>& mConfig)
{
    // Add installed module information:
    const auto modDir = fs::path(App::Application::getUserAppDataDir()) / "Mod";
    bool firstMod = true;
    if (fs::exists(modDir) && fs::is_directory(modDir)) {
        for (const auto& mod : fs::directory_iterator(modDir)) {
            if (!fs::is_directory(mod)) {
                continue;  // Ignore files, only show directories
            }
            addModuleInfo(str, QString::fromStdString(mod.path().string()), firstMod);
        }
    }
    const QString additionalModules = getValueOrEmpty(mConfig, "AdditionalModulePaths");

    if (!additionalModules.isEmpty()) {
        auto mods = additionalModules.split(QChar::fromLatin1(';'));
        for (const auto& mod : mods) {
            addModuleInfo(str, mod, firstMod);
        }
    }
}

}  // namespace Gui::VerboseInfoQt

#endif  // GUI_VERBOSE_INFO_QT_H
