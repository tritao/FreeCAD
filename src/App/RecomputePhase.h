// SPDX-License-Identifier: LGPL-2.1-or-later

#pragma once

namespace App
{

/**
 * @brief Semantic phases of a single document recompute cycle.
 *
 * A document recompute now runs in topo order within each phase, progressing
 * from `Normal` to `Finalize`. Objects may request one additional same-cycle
 * recompute in their current phase or a later phase, but never an earlier one.
 *
 * Intended usage:
 * - `Normal`: default producer phase for ordinary object recomputes
 * - `PostUpstream`: consumers that need upstream topology or links to settle
 * - `PostGeometry`: consumers that require derived geometry extracted first
 * - `Finalize`: final layout, annotation, or other end-of-cycle consumers
 *
 * `Idle` means no document recompute is currently active.
 *
 * This phase model is the public scheduling contract. Legacy `Recompute2`
 * remains an internal fallback indicator for a second pass inside the same
 * phase and should not be used as the primary semantic contract for new code.
 */
enum class RecomputePhase : signed char
{
    Idle = -1,
    Normal = 0,
    PostUpstream = 1,
    PostGeometry = 2,
    Finalize = 3,
};

constexpr bool isActiveRecomputePhase(RecomputePhase phase)
{
    return static_cast<int>(phase) >= static_cast<int>(RecomputePhase::Normal);
}

constexpr bool recomputePhasePrecedes(RecomputePhase lhs, RecomputePhase rhs)
{
    return static_cast<int>(lhs) < static_cast<int>(rhs);
}

constexpr RecomputePhase maxRecomputePhase(RecomputePhase lhs, RecomputePhase rhs)
{
    return recomputePhasePrecedes(lhs, rhs) ? rhs : lhs;
}

constexpr RecomputePhase nextRecomputePhase(RecomputePhase phase)
{
    switch (phase) {
        case RecomputePhase::Idle:
            return RecomputePhase::Normal;
        case RecomputePhase::Normal:
            return RecomputePhase::PostUpstream;
        case RecomputePhase::PostUpstream:
            return RecomputePhase::PostGeometry;
        case RecomputePhase::PostGeometry:
            return RecomputePhase::Finalize;
        case RecomputePhase::Finalize:
            return RecomputePhase::Finalize;
    }

    return RecomputePhase::Finalize;
}

constexpr const char* recomputePhaseName(RecomputePhase phase)
{
    switch (phase) {
        case RecomputePhase::Idle:
            return "Idle";
        case RecomputePhase::Normal:
            return "Normal";
        case RecomputePhase::PostUpstream:
            return "PostUpstream";
        case RecomputePhase::PostGeometry:
            return "PostGeometry";
        case RecomputePhase::Finalize:
            return "Finalize";
    }

    return "Unknown";
}

}  // namespace App
