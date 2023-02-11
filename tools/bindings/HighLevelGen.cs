using CppSharp.AST;
using CppSharp.AST.Extensions;
using CppSharp.Generators;
using CppSharp.Passes;
using FreeCAD;

namespace CppSharp
{
    class HighLevelGen : ILibrary
    {
        public readonly GeneratorKind GeneratorKind;

        public readonly TargetPlatform TargetPlatform;

        public HighLevelGen(GeneratorKind kind, TargetPlatform platform)
        {
            GeneratorKind = kind;
            TargetPlatform = platform;
        }

        public void Setup(Driver driver)
        {
            var options = driver.Options;
            
            var module = options.AddModule("FreeCAD");
            module.LibraryName = "FreeCAD";

            var path = Path.Combine("gen/cplusplus/x86_64-pc-linux-gnu");
            var headers = Directory.GetFiles(path, "*.h", SearchOption.AllDirectories);
            module.Headers.AddRange(headers);
            module.IncludeDirs.Add(path);

            Program.Setup(driver, module, TargetPlatform);

            var cppsharpIncludePath = Path.Combine("../../include");
            module.IncludeDirs.Add(cppsharpIncludePath);

            var parserOptions = driver.ParserOptions;
            parserOptions.UnityBuild = true;
            parserOptions.SkipLayoutInfo = true;
            //parserOptions.Verbose = true;

            options.OutputDir = Path.Combine("gen/", GeneratorKind.ToString().ToLowerInvariant());
            options.GenerateDeprecatedDeclarations = false;
            options.GenerationOutputMode = GenerationOutputMode.FilePerUnit;
            options.CompileCode = false;
            options.GenerateClassTemplates = true;
            options.GeneratorKind = GeneratorKind;
            options.UseHeaderDirectories = true;
        }

        public void SetupPasses(Driver driver)
        {
        }

        public void GenerateCode(Driver driver, List<GeneratorOutput> outputs)
        {
        }

        public void Preprocess(Driver driver, ASTContext ctx)
        {
            new IgnoreDecls(ctx).VisitASTContext(ctx);
            new IgnoreNativeConstructors().VisitASTContext(ctx);

            foreach (var unit in ctx.TranslationUnits)
            {
                if (unit.IsSystemHeader)
                    continue;
                
                var path = unit.FileRelativeDirectory;
                if (!path.StartsWith("ozone"))
                    unit.ExplicitlyIgnore();
            }

            ctx.IgnoreHeadersWithName("eventhandlers.h");

            //var fastDelegatesUnit = ctx.TranslationUnits.Find(unit => unit.FileNameWithoutExtension == "FastDelegates");
            //fastDelegatesUnit.ExplicitlyIgnore();
        }

        public void Postprocess(Driver driver, ASTContext ctx)
        {
        }
    }

    class IgnoreDecls : TranslationUnitPass
    {
        private ASTContext astContext;

        public IgnoreDecls(ASTContext context)
        {
            astContext = context;

            // app.h
            astContext.IgnoreClassMethodWithName("AppConsole", "Initialize");
            astContext.IgnoreClassMethodWithName("AppConsole", "OnAssert");
            astContext.IgnoreClassMethodWithName("AppConsole", "OnAssertFailure");

            astContext.IgnoreClassMethodWithName("App", "Initialize");
            astContext.IgnoreClassMethodWithName("App", "OnAssert");
            astContext.IgnoreClassMethodWithName("App", "OnAssertFailure");
            astContext.IgnoreClassMethodWithName("App", "GetXVisualInfo");

            astContext.IgnoreClassWithName("PointList");
            astContext.IgnoreClassWithName("WindowList");
            
            astContext.IgnoreClassMethodWithName("GraphicsBitmap", "GetNativeBitmap");

            astContext.IgnoreClassMethodWithName("GraphicsMatrix", "Get");
            astContext.IgnoreClassMethodWithName("GraphicsMatrix", "GetNativeMatrix");
            astContext.IgnoreClassMethodWithName("GraphicsMatrix", "TransformDistance");
            astContext.IgnoreClassMethodWithName("GraphicsMatrix", "TransformPoint");

            astContext.IgnoreClassMethodWithName("GraphicsPath", "GetCurrentPoint");
            astContext.IgnoreClassMethodWithName("GraphicsPath", "GetNativePath");
            astContext.IgnoreClassMethodWithName("GraphicsPath", "UnGetNativePath");
            
            astContext.IgnoreClassMethodWithName("GraphicsContext", "GetClipBox");
            astContext.IgnoreClassMethodWithName("GraphicsContext", "GetNativeContext");
            astContext.IgnoreClassMethodWithName("GraphicsContext", "CreateFromNative");
            astContext.IgnoreClassMethodWithName("GraphicsContext", "CreateFromNativeWindow");
            astContext.IgnoreClassMethodWithName("GraphicsContext", "CreateFromNativeHDC");
            astContext.IgnoreClassMethodWithName("GraphicsContext", "CreateContextFromNative");

            astContext.IgnoreClassMethodWithName("GraphicsRenderer", "CreateContextFromNativeContext");
            astContext.IgnoreClassMethodWithName("GraphicsRenderer", "CreateContextFromNativeWindow");
            astContext.IgnoreClassMethodWithName("GraphicsRenderer", "CreateBitmapFromNativeBitmap");
            astContext.IgnoreClassMethodWithName("GraphicsRenderer", "GetVersion");

            astContext.IgnoreClassMethodWithName("DC", "GetHandle");

            astContext.IgnoreClassMethodWithName("GridSizer", "CalcRowsCols");
        }

        public override bool VisitClassDecl(Class @class)
        {
            return base.VisitClassDecl(@class);
        }

        public override bool VisitFunctionDecl(Function function)
        {
            void IgnoreFunctionWithPointerParams(string pattern)
            {
                if (!function.IsGenerated)
                    return;

                if (!function.Name.StartsWith(pattern))
                    return;

                if (function.Parameters.Any(p => p.Type.IsPointer()))
                    function.ExplicitlyIgnore();
            }

            void IgnoreFunctionWithPointerReturn(string pattern)
            {
                if (!function.Name.StartsWith(pattern))
                    return;

                if (function.ReturnType.Type.IsPointer())
                    function.ExplicitlyIgnore();
            }

            if (function.IsOperator &&
               (function.OperatorKind == CXXOperatorKind.Conversion || function.OperatorKind == CXXOperatorKind.Equal))
            {
                //Diagnostics.Message(function.QualifiedName);
                function.ExplicitlyIgnore();
            }

            if (function.Name == "GetClientData")
                function.ExplicitlyIgnore();

            if (function.Name == "SetClientData")
                function.ExplicitlyIgnore();

            // gdicmn.h
            IgnoreFunctionWithPointerParams("DisplaySize");
            IgnoreFunctionWithPointerParams("ClientDisplayRect");

            // window.h
            IgnoreFunctionWithPointerParams("GetPosition");
            IgnoreFunctionWithPointerParams("GetScreenPosition");
            IgnoreFunctionWithPointerParams("GetSize");
            IgnoreFunctionWithPointerParams("GetBestSize");
            IgnoreFunctionWithPointerParams("GetClientSize");
            IgnoreFunctionWithPointerParams("GetVirtualSize");
            IgnoreFunctionWithPointerParams("ClientToScreen");
            IgnoreFunctionWithPointerParams("ScreenToClient");
            IgnoreFunctionWithPointerParams("LayoutPhase1");
            IgnoreFunctionWithPointerParams("LayoutPhase2");

            // toplevel.h
            IgnoreFunctionWithPointerParams("GetRectForTopLevelChildren");

            // colour.h
            IgnoreFunctionWithPointerParams("MakeMono");
            IgnoreFunctionWithPointerParams("MakeDisabled");
            IgnoreFunctionWithPointerParams("MakeGrey");
            IgnoreFunctionWithPointerParams("AlphaBlend");
            IgnoreFunctionWithPointerParams("ChangeLightness");

            // pen.h
            IgnoreFunctionWithPointerParams("GetDashes");
            IgnoreFunctionWithPointerParams("SetDashes");
            IgnoreFunctionWithPointerReturn("GetDash");

            // graphics.h
            IgnoreFunctionWithPointerParams("GetCurrentPoint");
            IgnoreFunctionWithPointerParams("GetBox");
            IgnoreFunctionWithPointerParams("GetDPI");
            IgnoreFunctionWithPointerParams("GetSize");
            IgnoreFunctionWithPointerParams("GetTextExtent");

            // dc.h
            IgnoreFunctionWithPointerParams("GetClippingBox");
            IgnoreFunctionWithPointerParams("GetUserScale");
            IgnoreFunctionWithPointerParams("GetLogicalScale");
            IgnoreFunctionWithPointerParams("GetLogicalOrigin");
            IgnoreFunctionWithPointerParams("GetDeviceOrigin");

            // sizer.h
            IgnoreFunctionWithPointerParams("CalcRowsCols");

            return true;
        }
    }

    class IgnoreNativeConstructors : TranslationUnitPass
    {
        public override bool VisitMethodDecl(Method method)
        {
            if (!method.IsConstructor)
                return true;

            if (method.Parameters.Count != 2)
                return true;

            if (method.Parameters[1].Name != "ownNativeInstance")
                return true;

            method.ExplicitlyIgnore();
            return true;
        }
    }
}