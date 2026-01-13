// SPDX-License-Identifier: LGPL-2.1-or-later
/****************************************************************************
 *   Copyright (c) 2017 Zheng Lei (realthunder) <realthunder.dev@gmail.com> *
 *                                                                          *
 *   This file is part of the FreeCAD CAx development system.               *
 *                                                                          *
 *   This library is free software; you can redistribute it and/or          *
 *   modify it under the terms of the GNU Library General Public            *
 *   License as published by the Free Software Foundation; either           *
 *   version 2 of the License, or (at your option) any later version.       *
 *                                                                          *
 *   This library  is distributed in the hope that it will be useful,       *
 *   but WITHOUT ANY WARRANTY; without even the implied warranty of         *
 *   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the          *
 *   GNU Library General Public License for more details.                   *
 *                                                                          *
 *   You should have received a copy of the GNU Library General Public      *
 *   License along with this library; see the file COPYING.LIB. If not,     *
 *   write to the Free Software Foundation, Inc., 59 Temple Place,          *
 *   Suite 330, Boston, MA  02111-1307, USA                                 *
 *                                                                          *
 ****************************************************************************/

#ifndef PATH_AreaParams_H
#define PATH_AreaParams_H

// define this to enable offset algo selection
// #define AREA_OFFSET_ALGO

/** \file
 * Parameters definition for Path::Area and its companion
 * See \ref ParamPage "here" for details of parameter definition.
 */

#include "ParamsHelper.h"
#include <clipper2/clipper.h>

/** clipper fill type */
#define AREA_CLIPPER_FILL_SEQ \
    (Clipper2Lib::FillRule::NonZero, \
     Clipper2Lib::FillRule::EvenOdd, \
     Clipper2Lib::FillRule::Positive, \
     Clipper2Lib::FillRule::Negative)
#define AREA_CLIPPER_FILL_INFO (Clipper2Lib::FillRule, Clipper2Lib::FillRule::)

/** Parameters of clipper fill types */
#define AREA_PARAMS_CLIPPER_FILL(_apply, _tail, ...) \
    _apply( \
        __VA_ARGS__, \
        FC_PP_IF(_tail, 1, 0), \
        (enum2, \
         subject_fill, \
         SubjectFill, \
         Clipper2Lib::FillRule::NonZero, \
         "Clipper2 subject fill rule. \nSee " \
         "http://www.angusj.com/clipper2/Docs/Units/Clipper/Types/FillRule.htm", \
         AREA_CLIPPER_FILL_SEQ, \
         AREA_CLIPPER_FILL_INFO) \
    ) \
        _apply( \
            __VA_ARGS__, \
            1, \
            (enum2, \
             clip_fill, \
             ClipFill, \
             Clipper2Lib::FillRule::NonZero, \
             "Clipper2 clip fill rule. \nSee " \
             "http://www.angusj.com/clipper2/Docs/Units/Clipper/Types/FillRule.htm", \
             AREA_CLIPPER_FILL_SEQ, \
             AREA_CLIPPER_FILL_INFO) \
        )

/** Deflection parameter */
#define AREA_PARAMS_DEFLECTION(_apply, _tail, ...) \
    _apply( \
        __VA_ARGS__, \
        FC_PP_IF(_tail, 1, 0), \
        (double, \
         deflection, \
         Deflection, \
         0.01, \
         "Deflection for non circular curve discretization. It also also used for\n" \
         "discretizing circular wires when you 'Explode' the shape for wire operations", \
         App::PropertyPrecision) \
    )

/** Base parameters */
#define AREA_PARAMS_BASE(_apply, _tail, ...) \
    _apply( \
        __VA_ARGS__, \
        FC_PP_IF(_tail, 1, 0), \
        (enum, \
         fill, \
         Fill, \
         2, \
         "Fill the output wires to make a face. \n" \
         "Auto means make a face if any of the children has a face.", \
         (None, Face, Auto)) \
    ) \
        _apply( \
            __VA_ARGS__, \
            1, \
            (enum, \
             coplanar, \
             Coplanar, \
             2, \
             "Specifies the way to check coplanar. 'Force' will discard non coplaner shapes,\n" \
             "but 'Check' only gives warning.", \
             (None, Check, Force)) \
        ) \
            _apply( \
                __VA_ARGS__, \
                1, \
                (bool, \
                 reorient, \
                 Reorient, \
                 true, \
                 "Re-orient closed wires in wire only shapes so that inner wires become holes.") \
            ) _apply(__VA_ARGS__, 1, (bool, outline, Outline, false, "Remove all inner wires (holes) before output the final shape")) \
                _apply( \
                    __VA_ARGS__, \
                    1, \
                    (bool, \
                     explode, \
                     Explode, \
                     false, \
                     "If true, Area will explode the first shape into disconnected open edges, \n" \
                     "with all curves discretized, so that later operations like 'Difference' \n" \
                     "behave like wire cutting. Without exploding, 'Difference' in Clipper2\n" \
                     "behave like face cutting.") \
                ) \
                    _apply( \
                        __VA_ARGS__, \
                        1, \
                        (enum, \
                         open_mode, \
                         OpenMode, \
                         0, \
                         "Specify how to handle open wires. 'None' means combine without " \
                         "openeration.\n" \
                         "'Edges' means separate to edges before Union. Clipper2 seems to have " \
                         "an.\n" \
                         "urge to close open wires.", \
                         (None, Union, Edges)) \
                    ) AREA_PARAMS_DEFLECTION(_apply, 1, __VA_ARGS__) \
                        AREA_PARAMS_CLIPPER_FILL(_apply, 1, __VA_ARGS__)

#define AREA_PARAMS_FIT_ARCS(_apply, _tail, ...) \
    _apply(__VA_ARGS__, FC_PP_IF(_tail, 1, 0), (bool, fit_arcs, FitArcs, true, "Enable arc fitting"))

/** libarea algorithm option parameters */
#define AREA_PARAMS_CAREA(_apply, _tail, ...) \
    _apply( \
        __VA_ARGS__, \
        FC_PP_IF(_tail, 1, 0), \
        (double, \
         tolerance, \
         Tolerance, \
         Precision::Confusion(), \
         "Point coincidence tolerance", \
         App::PropertyPrecision) \
    ) AREA_PARAMS_FIT_ARCS(_apply, 1, __VA_ARGS__) \
        _apply( \
            __VA_ARGS__, \
            1, \
            (bool, \
             clipper_simple, \
             Simplify, \
             false, \
             "Simplify polygons after operation. See https://goo.gl/Mh9XK1") \
        ) \
            _apply( \
                __VA_ARGS__, \
                1, \
                (double, \
                 clipper_clean_distance, \
                 CleanDistance, \
                 0.0, \
                 "Clean polygon smaller than this distance. See https://goo.gl/jox3JY", \
                 App::PropertyLength) \
            ) \
                _apply( \
                    __VA_ARGS__, \
                    1, \
                    (double, accuracy, Accuracy, 0.01, "Arc fitting accuracy", App::PropertyPrecision) \
                ) \
                    _apply( \
                        __VA_ARGS__, \
                        1, \
                        (double, units, Unit, 1.0, "Scaling factor for conversion to inch", App::PropertyFloat) \
                    ) \
                        _apply( \
                            __VA_ARGS__, \
                            1, \
                            (short, min_arc_points, MinArcPoints, 4, "Minimum segments for arc discretization") \
                        ) \
                            _apply( \
                                __VA_ARGS__, \
                                1, \
                                (short, \
                                 max_arc_points, \
                                 MaxArcPoints, \
                                 100, \
                                 "Maximum segments for arc discretization (ignored currently)") \
                            ) \
                                _apply( \
                                    __VA_ARGS__, \
                                    1, \
                                    (double, \
                                     clipper_scale, \
                                     ClipperScale, \
                                     1e7, \
                                     "Clipper2 operations are integer based. This is the scale " \
                                     "factor to convert\n" \
                                     "floating points.", \
                                     App::PropertyFloat) \
                                )

/** Pocket parameters
 *
 * These parameters corresponds to CAreaPocketParams in libarea
 * */
#define AREA_PARAMS_POCKET(_apply, _tail, ...) \
    _apply( \
        __VA_ARGS__, \
        FC_PP_IF(_tail, 1, 0), \
        (enum, \
         mode, \
         PocketMode, \
         0, \
         "Selects the pocket toolpath pattern", \
         (None, ZigZag, Offset, Spiral, ZigZagOffset, Line, Grid, Triangle)) \
    ) \
        _apply( \
            __VA_ARGS__, \
            1, \
            (double, tool_radius, ToolRadius, 1.0, "Tool radius for pocketing", App::PropertyLength) \
        ) \
            _apply( \
                __VA_ARGS__, \
                1, \
                (double, \
                 extra_offset, \
                 PocketExtraOffset, \
                 0.0, \
                 "Extra offset for pocketing", \
                 App::PropertyDistance) \
            ) \
                _apply( \
                    __VA_ARGS__, \
                    1, \
                    (double, \
                     stepover, \
                     PocketStepover, \
                     0.0, \
                     "Cutter diameter to step over on each pass. If =0, use ToolRadius.", \
                     App::PropertyLength) \
                ) _apply(__VA_ARGS__, 1, (bool, from_center, FromCenter, false, "Start pocketing from center")) \
                    _apply( \
                        __VA_ARGS__, \
                        1, \
                        (double, angle, Angle, 45, "Pattern angle in degree", App::PropertyAngle) \
                    ) \
                        _apply( \
                            __VA_ARGS__, \
                            1, \
                            (double, \
                             angle_shift, \
                             AngleShift, \
                             0.0, \
                             "Pattern angle shift for each section", \
                             App::PropertyAngle) \
                        ) \
                            _apply( \
                                __VA_ARGS__, \
                                1, \
                                (double, \
                                 shift, \
                                 Shift, \
                                 0.0, \
                                 "Pattern shift distance for each section.\n" \
                                 "The pocket pattern will be shifted in orthogonal direction by " \
                                 "this amount for each section.\n" \
                                 "This gives a 3D pattern mainly for 3D printing. The shift only " \
                                 "applies to 'Offset', 'Grid'\n" \
                                 "and 'Triangle'", \
                                 App::PropertyDistance) \
                            ) \
                                _apply( \
                                    __VA_ARGS__, \
                                    1, \
                                    (bool, \
                                     force_max_stepover, \
                                     ForceMaxStepover, \
                                     false, \
                                     "Force maximum stepover even if not all area is cleared. " \
                                     "Without this flag set, the " \
                                     "stepover may be reduced (for large stepover, >50%) to " \
                                     "ensure full area coverage") \
                                )

#define AREA_PARAMS_POCKET_CONF(_apply, _tail, ...) \
    _apply( \
        __VA_ARGS__, \
        FC_PP_IF(_tail, 1, 0), \
        (bool, thicken, Thicken, false, "Thicken the resulting wires with ToolRadius") \
    )

/** Operation code */
#define AREA_PARAMS_OPCODE(_apply, _tail, ...) \
    _apply( \
        __VA_ARGS__, \
        FC_PP_IF(_tail, 1, 0), \
        (enum, \
         op, \
         Operation, \
         0, \
         "Boolean operation.\n" \
         "For the first four operations, see " \
         "http://www.angusj.com/clipper2/Docs/Units/Clipper/Types/ClipType.htm.\n" \
         "'Compound' means no operation, normally used to do Area.sortWires().", \
         (Union, Difference, Intersection, Xor, Compound)) \
    )

/** Offset parameters */
#define AREA_PARAMS_OFFSET(_apply, _tail, ...) \
    _apply( \
        __VA_ARGS__, \
        FC_PP_IF(_tail, 1, 0), \
        (double, \
         offset, \
         Offset, \
         0.0, \
         "Offset value, positive for expansion, negative for shrinking", \
         App::PropertyDistance) \
    ) _apply(__VA_ARGS__, 1, (long, extra_pass, ExtraPass, 0, "Number of extra offset pass to generate.")) \
        _apply( \
            __VA_ARGS__, \
            1, \
            (double, \
             stepover, \
             Stepover, \
             0.0, \
             "Cutter diameter to step over on each pass. If =0, use Offset", \
             App::PropertyLength) \
        )

#define AREA_PARAMS_SECTION_EXTRA(_apply, _tail, ...) \
    _apply( \
        __VA_ARGS__, \
        FC_PP_IF(_tail, 1, 0), \
        (enum, \
         mode, \
         SectionMode, \
         2, \
         "Section offset coordinate mode.\n" \
         "'Absolute' means the absolute Z height (given in SectionOffset) to start slicing.\n" \
         "'BoundBox' means relative Z height to the bounding box of all the children shape.\n" \
         "'Workplane' means relative to workplane, minus SectionOffset.\n" \
         "Note that OCC has trouble getting the minimum bounding box of some solids, " \
         "particularly\n" \
         "those with non-planar surface. It is recommended to use Workplane to specify the " \
         "intended\n" \
         "starting z height.\n", \
         (Absolute, BoundBox, Workplane)) \
    ) \
        _apply( \
            __VA_ARGS__, \
            1, \
            (bool, \
             project, \
             Project, \
             false, \
             "The section is produced by normal projecting the outline\n" \
             "of all added shapes to the section plane, instead of slicing.") \
        )

/** Section parameters */
#define AREA_PARAMS_SECTION(_apply, _tail, ...) \
    _apply( \
        __VA_ARGS__, \
        FC_PP_IF(_tail, 1, 0), \
        (long, count, SectionCount, 0, "Number of sections to generate. -1 means full sections.") \
    ) \
        _apply( \
            __VA_ARGS__, \
            1, \
            (double, \
             stepdown, \
             Stepdown, \
             1.0, \
             "Step down distance for each section.\n" \
             "Positive value means going from top down, and negative the other way round", \
             App::PropertyDistance) \
        ) \
            _apply( \
                __VA_ARGS__, \
                1, \
                (double, \
                 offset, \
                 SectionOffset, \
                 0.0, \
                 "Offset for the first section. The direction of the offset is\n" \
                 "determined by the section direction (i.e. the signess of Stepdown). If going " \
                 "from top " \
                 "down,\n" \
                 "a positive value means offset downward, and if bottom up, it means upward", \
                 App::PropertyDistance) \
            ) \
                _apply( \
                    __VA_ARGS__, \
                    1, \
                    (double, \
                     tolerance, \
                     SectionTolerance, \
                     1e-6, \
                     "Offset value added when hitting the boundary.\n" \
                     "When the section hits or over the shape boundary, a section with the " \
                     "height of that " \
                     "boundary\n" \
                     "will be created. A small offset is usually required to avoid the " \
                     "tangential cut.", \
                     App::PropertyPrecision) \
                ) AREA_PARAMS_SECTION_EXTRA(_apply, 1, __VA_ARGS__)

/** Offset configuration parameters */
#ifdef AREA_OFFSET_ALGO
# define AREA_PARAMS_OFFSET_CONF(_apply, _tail, ...) \
     _apply( \
         __VA_ARGS__, \
         FC_PP_IF(_tail, 1, 0), \
         (enum, algo, Algo, 0, "Offset algorithm type", (Clipper, libarea)) \
     ) \
         _apply( \
             __VA_ARGS__, \
             1, \
             (enum2, \
              join_type, \
              JoinType, \
              Clipper2Lib::JoinType::Round, \
              "Clipper2 offset join type. \nSee " \
              "http://www.angusj.com/clipper2/Docs/Units/Clipper/Types/JoinType.htm", \
              (Clipper2Lib::JoinType::Round, \
               Clipper2Lib::JoinType::Square, \
               Clipper2Lib::JoinType::Miter), \
              (Clipper2Lib::JoinType, Clipper2Lib::JoinType::)) \
         ) \
             _apply( \
                 __VA_ARGS__, \
                 1, \
                 (enum2, \
                  end_type, \
                  EndType, \
                  Clipper2Lib::EndType::Round, \
                  "\nClipper2 offset end type. See " \
                  "http://www.angusj.com/clipper2/Docs/Units/Clipper/Types/EndType.htm", \
                  (Clipper2Lib::EndType::Round, \
                   Clipper2Lib::EndType::Polygon, \
                   Clipper2Lib::EndType::Joined, \
                   Clipper2Lib::EndType::Square, \
                   Clipper2Lib::EndType::Butt), \
                  (Clipper2Lib::EndType, Clipper2Lib::EndType::)) \
             ) \
                 _apply( \
                     __VA_ARGS__, \
                     1, \
                     (double, \
                      miter_limit, \
                      MiterLimit, \
                      2.0, \
                      "Miter limit for joint type Miter. See " \
                      "http://www.angusj.com/clipper2/Docs/Units/Clipper.Offset/Classes/" \
                      "ClipperOffset/Properties/MiterLimit.htm", \
                      App::PropertyFloat) \
                 ) \
                     _apply( \
                         __VA_ARGS__, \
                         1, \
                         (double, \
                          round_precision, \
                          RoundPrecision, \
                          0.0, \
                          "Round joint precision. If =0, it defaults to Accuracy. \n" \
                          "See " \
                          "http://www.angusj.com/clipper2/Docs/Units/Clipper.Offset/Classes/" \
                          "ClipperOffset/" \
                          "Properties/ArcTolerance.htm", \
                          App::PropertyPrecision) \
                     )
#else
# define AREA_PARAMS_OFFSET_CONF(_apply, _tail, ...) \
     _apply( \
         __VA_ARGS__, \
         FC_PP_IF(_tail, 1, 0), \
         (enum2, \
          join_type, \
          JoinType, \
          Clipper2Lib::JoinType::Round, \
          "Clipper2 offset join type. \nSee " \
          "http://www.angusj.com/clipper2/Docs/Units/Clipper/Types/JoinType.htm", \
          (Clipper2Lib::JoinType::Round, Clipper2Lib::JoinType::Square, Clipper2Lib::JoinType::Miter), \
          (Clipper2Lib::JoinType, Clipper2Lib::JoinType::)) \
     ) \
         _apply( \
             __VA_ARGS__, \
             1, \
             (enum2, \
              end_type, \
              EndType, \
              Clipper2Lib::EndType::Round, \
              "\nClipper2 offset end type. See " \
              "http://www.angusj.com/clipper2/Docs/Units/Clipper/Types/EndType.htm", \
              (Clipper2Lib::EndType::Round, \
               Clipper2Lib::EndType::Polygon, \
               Clipper2Lib::EndType::Joined, \
               Clipper2Lib::EndType::Square, \
               Clipper2Lib::EndType::Butt), \
              (Clipper2Lib::EndType, Clipper2Lib::EndType::)) \
         ) \
             _apply( \
                 __VA_ARGS__, \
                 1, \
                 (double, \
                  miter_limit, \
                  MiterLimit, \
                  2.0, \
                  "Miter limit for joint type Miter. See " \
                  "http://www.angusj.com/clipper2/Docs/Units/Clipper.Offset/Classes/" \
                  "ClipperOffset/Properties/MiterLimit.htm", \
                  App::PropertyFloat) \
             ) \
                 _apply( \
                     __VA_ARGS__, \
                     1, \
                     (double, \
                      round_precision, \
                      RoundPrecision, \
                      0.0, \
                      "Round joint precision. If =0, it defaults to Accuracy. \n" \
                      "See " \
                      "http://www.angusj.com/clipper2/Docs/Units/Clipper.Offset/Classes/" \
                      "ClipperOffset/" \
                      "Properties/ArcTolerance.htm", \
                      App::PropertyPrecision) \
                 )
#endif

#define AREA_PARAMS_MIN_DIST(_apply, _tail, ...) \
    _apply( \
        __VA_ARGS__, \
        FC_PP_IF(_tail, 1, 0), \
        (double, \
         min_dist, \
         MinDistance, \
         0.0, \
         "minimum distance for the generated new wires. Wires maybe broken if the\n" \
         "algorithm see fits. Set to zero to disable wire breaking.", \
         App::PropertyLength) \
    )

/** Arc plane */
#define AREA_PARAMS_ARC_PLANE(_apply, _tail, ...) \
    _apply( \
        __VA_ARGS__, \
        FC_PP_IF(_tail, 1, 0), \
        (enum, \
         arc_plane, \
         ArcPlane, \
         1, \
         "Arc drawing plane, corresponding to G17, G18, and G19.\n" \
         "If not 'None', the output wires will be transformed to align with the selected plane,\n" \
         "and the corresponding GCode will be inserted.\n" \
         "'Auto' means the plane is determined by the first encountered arc plane. If the found\n" \
         "plane does not align to any GCode plane, XY plane is used.\n" \
         "'Variable' means the arc plane can be changed during operation to align to the\n" \
         "arc encountered.", \
         (None, Auto, XY, ZX, YZ, Variable)) \
    )

#define AREA_PARAMS_ORIENTATION(_apply, _tail, ...) \
    _apply( \
        __VA_ARGS__, \
        FC_PP_IF(_tail, 1, 0), \
        (enum, \
         orientation, \
         Orientation, \
         0, \
         "Enforce loop orientation\n" \
         "'Normal' means CCW for outer wires when looking against the positive axis direction, \n" \
         "and CW for inner wires. 'Reversed' means the other way round", \
         (Normal, Reversed)) \
    )

/** Area wire sorting parameters */
#define AREA_PARAMS_SORT(_apply, _tail, ...) \
    _apply( \
        __VA_ARGS__, \
        FC_PP_IF(_tail, 1, 0), \
        (enum, \
         sort_mode, \
         SortMode, \
         1, \
         "Wire sorting mode to optimize travel distance.\n" \
         "'2D5' explode shapes into wires, and groups the shapes by its plane. The 'start' " \
         "position\n" \
         "chooses the first plane to start. The algorithm will then sort within the plane and " \
         "then\n" \
         "move on to the next nearest plane.\n" \
         "'3D' makes no assumption of planarity. The sorting is done across 3D space.\n" \
         "'Greedy' like '2D5' but will try to minimize travel by searching for nearest path " \
         "below\n" \
         "the current milling layer. The path in lower layer is only selected if the moving " \
         "distance\n" \
         "is within the value given in 'threshold'.", \
         (None, 2D5, 3D, Greedy)) \
    ) AREA_PARAMS_MIN_DIST(_apply, 1, __VA_ARGS__) \
        _apply( \
            __VA_ARGS__, \
            1, \
            (double, \
             abscissa, \
             SortAbscissa, \
             3.0, \
             "Controls vertex sampling on wire for nearest point searching\n" \
             "The sampling is dong using OCC GCPnts_UniformAbscissa", \
             App::PropertyLength) \
        ) \
            _apply( \
                __VA_ARGS__, \
                1, \
                (short, nearest_k, NearestK, 3, "Nearest k sampling vertices are considered during sorting") \
            ) AREA_PARAMS_ORIENTATION(_apply, 1, __VA_ARGS__) \
                _apply( \
                    __VA_ARGS__, \
                    1, \
                    (enum, \
                     direction, \
                     Direction, \
                     0, \
                     "Enforce open path direction", \
                     (None, XPositive, XNegative, YPositive, YNegative, ZPositive, ZNegative)) \
                ) \
                    _apply( \
                        __VA_ARGS__, \
                        1, \
                        (double, \
                         threshold, \
                         RetractThreshold, \
                         0.0, \
                         "If two wire's end points are separated within this threshold, they are " \
                         "consider\n" \
                         "as connected. You may want to set this to the tool diameter to keep " \
                         "the tool down.", \
                         App::PropertyLength) \
                    ) \
                        _apply( \
                            __VA_ARGS__, \
                            1, \
                            (enum, retract_axis, RetractAxis, 2, "Tool retraction axis", (X, Y, Z)) \
                        )

/** Area path generation parameters */
#define AREA_PARAMS_PATH(_apply, _tail, ...) \
    AREA_PARAMS_ARC_PLANE(_apply, _tail, __VA_ARGS__) \
    AREA_PARAMS_SORT(_apply, 1, __VA_ARGS__) \
    _apply( \
        __VA_ARGS__, \
        1, \
        (double, \
         retraction, \
         Retraction, \
         0.0, \
         "Tool retraction absolute coordinate along retraction axis", \
         App::PropertyLength) \
    ) \
        _apply( \
            __VA_ARGS__, \
            1, \
            (double, \
             resume_height, \
             ResumeHeight, \
             0.0, \
             "When return from last retraction, this gives the pause height relative to the Z\n" \
             "value of the next move.", \
             App::PropertyLength) \
        ) \
            _apply( \
                __VA_ARGS__, \
                1, \
                (double, \
                 segmentation, \
                 Segmentation, \
                 0.0, \
                 "Break long curves into segments of this length. One use case is for PCB " \
                 "autolevel,\n" \
                 "so that more correction points can be inserted", \
                 App::PropertyLength) \
            ) _apply(__VA_ARGS__, 1, (double, feedrate, FeedRate, 0.0, "Normal move feed rate", App::PropertyFloat)) \
                _apply( \
                    __VA_ARGS__, \
                    1, \
                    (double, \
                     feedrate_v, \
                     FeedRateVertical, \
                     0.0, \
                     "Vertical only (step down) move feed rate", \
                     App::PropertyFloat) \
                ) \
                    _apply( \
                        __VA_ARGS__, \
                        1, \
                        (bool, \
                         verbose, \
                         Verbose, \
                         true, \
                         "If true, each motion GCode will contain full coordinate and feedrate") \
                    ) \
                        _apply( \
                            __VA_ARGS__, \
                            1, \
                            (bool, \
                             abs_center, \
                             AbsoluteArcCenter, \
                             false, \
                             "Use absolute arc center mode (G90.1)") \
                        ) _apply(__VA_ARGS__, 1, (bool, preamble, EmitPreamble, true, "Emit preambles")) \
                            AREA_PARAMS_DEFLECTION(_apply, 1, __VA_ARGS__)

/** Group of all Area configuration parameters except CArea's*/
#define AREA_PARAMS_AREA(_apply, _tail, ...) \
    AREA_PARAMS_BASE(_apply, _tail, __VA_ARGS__) \
    AREA_PARAMS_OFFSET(_apply, 1, __VA_ARGS__) \
    AREA_PARAMS_OFFSET_CONF(_apply, 1, __VA_ARGS__) \
    AREA_PARAMS_POCKET(_apply, 1, __VA_ARGS__) \
    AREA_PARAMS_POCKET_CONF(_apply, 1, __VA_ARGS__) \
    AREA_PARAMS_SECTION(_apply, 1, __VA_ARGS__)

/** Group of all Area configuration parameters */
#define AREA_PARAMS_CONF(_apply, _tail, ...) \
    AREA_PARAMS_CAREA(_apply, _tail, __VA_ARGS__) \
    AREA_PARAMS_AREA(_apply, 1, __VA_ARGS__)

/** Group of all Area parameters */
#define AREA_PARAMS_ALL(_apply, _tail, ...) \
    AREA_PARAMS_CONF(_apply, _tail, __VA_ARGS__) \
    AREA_PARAMS_OPCODE(_apply, 1, __VA_ARGS__)

#define AREA_PARAMS_STATIC_CONF AREA_PARAMS_CONF

#endif  // PATH_AreaParam_H
