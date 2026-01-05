// SPDX-License-Identifier: LGPL-2.1-or-later

#include "ConsoleQtBridge.h"

#include <QCoreApplication>
#include <QEventLoop>
#include <QMetaObject>
#include <QThread>

#include <Base/Console.h>

namespace
{

template<Base::LogStyle category>
void notifyConsoleMessage(
    const Base::IntendedRecipient recipient,
    const Base::ContentType content,
    const std::string& notifiername,
    const std::string& msg
)
{
    switch (recipient) {
        case Base::IntendedRecipient::All:
            switch (content) {
                case Base::ContentType::Untranslated:
                    Base::Console().notify<category, Base::IntendedRecipient::All, Base::ContentType::Untranslated>(
                        notifiername,
                        msg
                    );
                    return;
                case Base::ContentType::Translated:
                    Base::Console().notify<category, Base::IntendedRecipient::All, Base::ContentType::Translated>(
                        notifiername,
                        msg
                    );
                    return;
                case Base::ContentType::Untranslatable:
                    Base::Console()
                        .notify<category, Base::IntendedRecipient::All, Base::ContentType::Untranslatable>(
                            notifiername,
                            msg
                        );
                    return;
            }
            break;
        case Base::IntendedRecipient::User:
            switch (content) {
                case Base::ContentType::Untranslated:
                    Base::Console()
                        .notify<category, Base::IntendedRecipient::User, Base::ContentType::Untranslated>(
                            notifiername,
                            msg
                        );
                    return;
                case Base::ContentType::Translated:
                    Base::Console().notify<category, Base::IntendedRecipient::User, Base::ContentType::Translated>(
                        notifiername,
                        msg
                    );
                    return;
                case Base::ContentType::Untranslatable:
                    Base::Console()
                        .notify<category, Base::IntendedRecipient::User, Base::ContentType::Untranslatable>(
                            notifiername,
                            msg
                        );
                    return;
            }
            break;
        case Base::IntendedRecipient::Developer:
            switch (content) {
                case Base::ContentType::Untranslated:
                    Base::Console()
                        .notify<category, Base::IntendedRecipient::Developer, Base::ContentType::Untranslated>(
                            notifiername,
                            msg
                        );
                    return;
                case Base::ContentType::Translated:
                    Base::Console()
                        .notify<category, Base::IntendedRecipient::Developer, Base::ContentType::Translated>(
                            notifiername,
                            msg
                        );
                    return;
                case Base::ContentType::Untranslatable:
                    Base::Console()
                        .notify<category, Base::IntendedRecipient::Developer, Base::ContentType::Untranslatable>(
                            notifiername,
                            msg
                        );
                    return;
            }
            break;
    }
}

void deliverConsoleMessage(
    const Base::ConsoleSingleton::FreeCAD_ConsoleMsgType type,
    const Base::IntendedRecipient recipient,
    const Base::ContentType content,
    const std::string& notifiername,
    const std::string& msg
)
{
    switch (type) {
        case Base::ConsoleSingleton::MsgType_Txt:
            notifyConsoleMessage<Base::LogStyle::Message>(recipient, content, notifiername, msg);
            return;
        case Base::ConsoleSingleton::MsgType_Log:
            notifyConsoleMessage<Base::LogStyle::Log>(recipient, content, notifiername, msg);
            return;
        case Base::ConsoleSingleton::MsgType_Wrn:
            notifyConsoleMessage<Base::LogStyle::Warning>(recipient, content, notifiername, msg);
            return;
        case Base::ConsoleSingleton::MsgType_Err:
            notifyConsoleMessage<Base::LogStyle::Error>(recipient, content, notifiername, msg);
            return;
        case Base::ConsoleSingleton::MsgType_Critical:
            notifyConsoleMessage<Base::LogStyle::Critical>(recipient, content, notifiername, msg);
            return;
        case Base::ConsoleSingleton::MsgType_Notification:
            notifyConsoleMessage<Base::LogStyle::Notification>(recipient, content, notifiername, msg);
            return;
        default:
            return;
    }
}

}  // namespace

namespace App
{

void installConsoleQtBridge()
{
    Base::Console().setPostEventHandler(
        [](const Base::ConsoleSingleton::FreeCAD_ConsoleMsgType type,
           const Base::IntendedRecipient recipient,
           const Base::ContentType content,
           const std::string& notifiername,
           const std::string& msg) {
            QCoreApplication* app = QCoreApplication::instance();
            if (!app) {
                deliverConsoleMessage(type, recipient, content, notifiername, msg);
                return;
            }

            if (QThread::currentThread() == app->thread()) {
                deliverConsoleMessage(type, recipient, content, notifiername, msg);
                return;
            }

            QMetaObject::invokeMethod(
                app,
                [type, recipient, content, notifiername, msg]() {
                    deliverConsoleMessage(type, recipient, content, notifiername, msg);
                },
                Qt::QueuedConnection
            );
        }
    );

    Base::Console().setRefreshHandler([]() {
        QCoreApplication* app = QCoreApplication::instance();
        if (!app) {
            return;
        }

        const auto flags = QEventLoop::ExcludeUserInputEvents;
        if (QThread::currentThread() == app->thread()) {
            QCoreApplication::processEvents(flags);
            return;
        }

        // Best-effort: avoid blocking from background threads (can deadlock during shutdown).
        QMetaObject::invokeMethod(
            app,
            [flags]() { QCoreApplication::processEvents(flags); },
            Qt::QueuedConnection
        );
    });
}

}  // namespace App

