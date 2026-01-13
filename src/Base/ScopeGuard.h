// SPDX-License-Identifier: LGPL-2.1-or-later

#ifndef BASE_SCOPE_GUARD_H
#define BASE_SCOPE_GUARD_H

#include <type_traits>
#include <utility>

namespace Base
{

template <typename Fn>
class ScopeExit
{
public:
    explicit ScopeExit(Fn&& function)
        : function_(std::forward<Fn>(function))
    {}

    ScopeExit(const ScopeExit&) = delete;
    ScopeExit& operator=(const ScopeExit&) = delete;

    ScopeExit(ScopeExit&& other) noexcept(std::is_nothrow_move_constructible_v<Fn>)
        : function_(std::move(other.function_))
        , active_(other.active_)
    {
        other.active_ = false;
    }

    ScopeExit& operator=(ScopeExit&& other) noexcept(std::is_nothrow_move_assignable_v<Fn>)
    {
        if (this != &other) {
            if (active_) {
                function_();
            }
            function_ = std::move(other.function_);
            active_ = other.active_;
            other.active_ = false;
        }
        return *this;
    }

    ~ScopeExit()
    {
        if (active_) {
            function_();
        }
    }

    void release() noexcept
    {
        active_ = false;
    }

private:
    Fn function_;
    bool active_ {true};
};

template <typename Fn>
auto makeScopeExit(Fn&& function)
{
    return ScopeExit<std::decay_t<Fn>>(std::forward<Fn>(function));
}

}  // namespace Base

#endif  // BASE_SCOPE_GUARD_H

