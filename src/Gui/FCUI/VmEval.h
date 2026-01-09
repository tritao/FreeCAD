#pragma once

#include <QJsonArray>
#include <QVariant>
#include <QVariantMap>

class VmEval final {
public:
    QVariant eval(const QJsonArray& ops, const QVariantMap& selfProps, const QVariantMap& hostPaths) const;
};
