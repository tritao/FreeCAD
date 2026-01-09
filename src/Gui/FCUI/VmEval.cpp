#include "VmEval.h"

#include <algorithm>
#include <QJsonObject>
#include <QMetaType>
#include <QStringList>

namespace {

QVariant pop(QVector<QVariant>& stack) {
    const QVariant v = stack.back();
    stack.pop_back();
    return v;
}

QVariant add(const QVariant& a, const QVariant& b) {
    // Prefer string concat if either operand is string-ish.
    if (a.userType() == QMetaType::QString || b.userType() == QMetaType::QString) {
        return a.toString() + b.toString();
    }
    // Fall back to numeric.
    const double da = a.toDouble();
    const double db = b.toDouble();
    // If both look integral, keep int.
    if (a.canConvert<int>() && b.canConvert<int>() && a.toDouble() == double(a.toInt()) && b.toDouble() == double(b.toInt())) {
        return a.toInt() + b.toInt();
    }
    return da + db;
}

} // namespace

QVariant VmEval::eval(const QJsonArray& ops, const QVariantMap& selfProps, const QVariantMap& hostPaths) const {
    QVector<QVariant> stack;
    stack.reserve(ops.size());

    for (const auto& insVal : ops) {
        const auto ins = insVal.toObject();
        const auto op = ins.value("op").toString();

        if (op == "CONST") {
            stack.push_back(ins.value("value").toVariant());
            continue;
        }
        if (op == "LOAD_SELF") {
            stack.push_back(selfProps.value(ins.value("name").toString()));
            continue;
        }
        if (op == "LOAD_HOST_PATH") {
            stack.push_back(hostPaths.value(ins.value("path").toString()));
            continue;
        }
        if (op == "NOT") {
            stack.push_back(!pop(stack).toBool());
            continue;
        }
        if (op == "NEG") {
            stack.push_back(-pop(stack).toDouble());
            continue;
        }
        if (op == "POS") {
            stack.push_back(+pop(stack).toDouble());
            continue;
        }
        if (op == "ADD") {
            const auto b = pop(stack);
            const auto a = pop(stack);
            stack.push_back(add(a, b));
            continue;
        }
        if (op == "SUB") {
            const auto b = pop(stack).toDouble();
            const auto a = pop(stack).toDouble();
            stack.push_back(a - b);
            continue;
        }
        if (op == "MUL") {
            const auto b = pop(stack).toDouble();
            const auto a = pop(stack).toDouble();
            stack.push_back(a * b);
            continue;
        }
        if (op == "DIV") {
            const auto b = pop(stack).toDouble();
            const auto a = pop(stack).toDouble();
            stack.push_back(a / b);
            continue;
        }
        if (op == "MOD") {
            const auto b = pop(stack).toInt();
            const auto a = pop(stack).toInt();
            stack.push_back(a % b);
            continue;
        }
        if (op == "AND") {
            const auto b = pop(stack).toBool();
            const auto a = pop(stack).toBool();
            stack.push_back(a && b);
            continue;
        }
        if (op == "OR") {
            const auto b = pop(stack).toBool();
            const auto a = pop(stack).toBool();
            stack.push_back(a || b);
            continue;
        }
        if (op == "EQ") {
            const auto b = pop(stack);
            const auto a = pop(stack);
            stack.push_back(a == b);
            continue;
        }
        if (op == "NE") {
            const auto b = pop(stack);
            const auto a = pop(stack);
            stack.push_back(a != b);
            continue;
        }
        if (op == "LT") {
            const auto b = pop(stack).toDouble();
            const auto a = pop(stack).toDouble();
            stack.push_back(a < b);
            continue;
        }
        if (op == "LE") {
            const auto b = pop(stack).toDouble();
            const auto a = pop(stack).toDouble();
            stack.push_back(a <= b);
            continue;
        }
        if (op == "GT") {
            const auto b = pop(stack).toDouble();
            const auto a = pop(stack).toDouble();
            stack.push_back(a > b);
            continue;
        }
        if (op == "GE") {
            const auto b = pop(stack).toDouble();
            const auto a = pop(stack).toDouble();
            stack.push_back(a >= b);
            continue;
        }
        if (op == "SELECT") {
            const auto elseV = pop(stack);
            const auto thenV = pop(stack);
            const auto cond = pop(stack).toBool();
            stack.push_back(cond ? thenV : elseV);
            continue;
        }
        if (op == "CALL_BUILTIN") {
            const auto name = ins.value("name").toString();
            const int argc = ins.value("argc").toInt();
            QVector<QVariant> args;
            args.reserve(argc);
            for (int i = 0; i < argc; i++) {
                args.push_back(pop(stack));
            }
            std::reverse(args.begin(), args.end());

            if (name == "str") {
                stack.push_back(args.value(0).toString());
                continue;
            }
            if (name == "len") {
                const auto v = args.value(0);
                if (v.userType() == QMetaType::QString) {
                    stack.push_back(v.toString().size());
                } else if (v.canConvert<QVariantList>()) {
                    stack.push_back(v.toList().size());
                } else {
                    stack.push_back(0);
                }
                continue;
            }
            if (name == "min" || name == "max") {
                double best = args.value(0).toDouble();
                for (int i = 1; i < args.size(); i++) {
                    const double d = args[i].toDouble();
                    best = (name == "min") ? std::min(best, d) : std::max(best, d);
                }
                stack.push_back(best);
                continue;
            }
            if (name == "format") {
                // Minimal placeholder: "format('{0}', x)" -> QString::arg
                QString fmt = args.value(0).toString();
                for (int i = 1; i < args.size(); i++) {
                    fmt = fmt.arg(args[i].toString());
                }
                stack.push_back(fmt);
                continue;
            }

            stack.push_back(QVariant());
            continue;
        }

        // Unknown op: push null to keep going (viewer is best-effort).
        stack.push_back(QVariant());
    }

    return stack.isEmpty() ? QVariant() : stack.back();
}
