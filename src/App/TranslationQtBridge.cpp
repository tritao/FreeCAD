// SPDX-License-Identifier: LGPL-2.1-or-later

#include "TranslationQtBridge.h"

#include <QCoreApplication>
#include <QMetaObject>
#include <QThread>
#include <QTranslator>

#include <mutex>
#include <unordered_map>
#include <utility>
#include <vector>

#include <Base/Translation.h>

namespace
{

struct InstalledTranslator
{
    std::unique_ptr<QTranslator> translator;
};

std::mutex translatorsMutex;
std::unordered_map<std::string, std::vector<InstalledTranslator>> translatorsByFile;

bool installTranslatorImpl(const std::string& filename)
{
    QCoreApplication* app = QCoreApplication::instance();
    if (!app) {
        return false;
    }

    auto translator = std::make_unique<QTranslator>(nullptr);
    if (!translator->load(QString::fromUtf8(filename.c_str()))) {
        return false;
    }

    if (!app->installTranslator(translator.get())) {
        return false;
    }

    std::lock_guard<std::mutex> lock(translatorsMutex);
    translatorsByFile[filename].push_back({std::move(translator)});
    return true;
}

bool removeTranslatorsImpl(const std::vector<std::string>& filenames)
{
    QCoreApplication* app = QCoreApplication::instance();
    if (!app) {
        return false;
    }

    std::vector<std::unique_ptr<QTranslator>> toRemove;
    {
        std::lock_guard<std::mutex> lock(translatorsMutex);
        for (const auto& filename : filenames) {
            auto it = translatorsByFile.find(filename);
            if (it == translatorsByFile.end()) {
                continue;
            }
            for (auto& entry : it->second) {
                toRemove.push_back(std::move(entry.translator));
            }
            translatorsByFile.erase(it);
        }
    }

    bool ok = true;
    for (const auto& t : toRemove) {
        ok &= app->removeTranslator(t.get());
    }
    return ok;
}

}  // namespace

namespace App
{

void installTranslationQtBridge()
{
    Base::Translation::setTranslateHandler(
        [](std::string_view context,
           std::string_view sourceText,
           std::string_view disambiguation,
           int n) {
            const QString translated = QCoreApplication::translate(
                std::string(context).c_str(),
                std::string(sourceText).c_str(),
                disambiguation.empty() ? nullptr : std::string(disambiguation).c_str(),
                n
            );
            return translated.toStdString();
        }
    );

    Base::Translation::setInstallTranslatorHandler([](std::string_view filename) {
        const std::string file(filename);
        QCoreApplication* app = QCoreApplication::instance();
        if (!app || QThread::currentThread() == app->thread()) {
            return installTranslatorImpl(file);
        }

        bool ok = false;
        QMetaObject::invokeMethod(
            app,
            [&ok, file]() { ok = installTranslatorImpl(file); },
            Qt::BlockingQueuedConnection
        );
        return ok;
    });

    Base::Translation::setRemoveTranslatorsHandler([](const std::vector<std::string>& filenames) {
        QCoreApplication* app = QCoreApplication::instance();
        if (!app || QThread::currentThread() == app->thread()) {
            return removeTranslatorsImpl(filenames);
        }

        bool ok = false;
        QMetaObject::invokeMethod(
            app,
            [&ok, filenames]() { ok = removeTranslatorsImpl(filenames); },
            Qt::BlockingQueuedConnection
        );
        return ok;
    });
}

}  // namespace App
