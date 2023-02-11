using System.Text.RegularExpressions;
using CppSharp;
using CppSharp.AST;
using CppSharp.AST.Extensions;
using CppSharp.Generators;
using CppSharp.Passes;

namespace FreeCAD
{
    static class Program
    {
        public static string FreeCADPath => "/home/joao/dev/FreeCAD";
        public static string FreeCADBuildMode => "Release";

        public static void Main(string[] args)
        {
            const TargetPlatform targetPlatform = TargetPlatform.Linux;
            ConsoleDriver.Run(new LowLevelGen(GeneratorKind.Emscripten, targetPlatform));
            //ConsoleDriver.Run(new HighLevelGen(GeneratorKind.QuickJS, targetPlatform));
            //ConsoleDriver.Run(new HighLevelGen(GeneratorKind.TypeScript, targetPlatform));
            //ConsoleDriver.Run(new HighLevelGen(GeneratorKind.CSharp, targetPlatform));
        }

        public static string GetExamplesDirectory(string name)
        {
            var directory = Directory.GetParent(Directory.GetCurrentDirectory());
            while (directory != null)
            {
                var path = Path.Combine(directory.FullName, "examples", name);
                if (Directory.Exists(path))
                    return path;

                directory = directory.Parent;
            }

            throw new Exception($"Examples directory for project '{name}' was not found");
        }

        public static void Setup(Driver driver, Module module, TargetPlatform targetPlatform)
        {
            // TODO: Replace this with compile_commands.json parser.

            var includePath = Path.Combine(FreeCADPath, "src");
            module.IncludeDirs.Add(includePath);

            var buildPath = Path.Combine(FreeCADPath, $"build");
            if (!Directory.Exists(buildPath))
                throw new Exception("Expected build directory: " + buildPath);
            module.IncludeDirs.Add(buildPath);

            var buildIncludePath = Path.Combine(buildPath, "src");
            if (!Directory.Exists(buildIncludePath))
                throw new Exception("Expected build directory: " + buildIncludePath);
            module.IncludeDirs.Add(buildIncludePath);

            // Third party dependencies
            
            var thirdPartyPath = Path.Combine(FreeCADPath, "third_party");
            var qtBase = Path.Combine(thirdPartyPath, "qtbase");
            module.IncludeDirs.Add(Path.Combine(qtBase, "include"));
            module.IncludeDirs.Add(Path.Combine(qtBase, "build_em/include"));
            module.IncludeDirs.Add(Path.Combine(qtBase, "build_em/include/QtCore"));

            var parserOptions = driver.ParserOptions;
            parserOptions.AddArguments("-fcxx-exceptions");

            parserOptions.TargetTriple = targetPlatform switch
            {
                TargetPlatform.MacOS => "i686-apple-darwin",
                TargetPlatform.Linux => "x86_64-pc-linux-gnu",
                TargetPlatform.Emscripten => "wasm32-emscripten",
                _ => parserOptions.TargetTriple
            };

            parserOptions.AddIncludeDirs(includePath);
        }
    }

    class LowLevelGen : ILibrary
    {
        public GeneratorKind GeneratorKind;

        public TargetPlatform TargetPlatform;

        public LowLevelGen(GeneratorKind kind, TargetPlatform platform)
        {
            GeneratorKind = kind;
            TargetPlatform = platform;
        }

        public void Setup(Driver driver)
        {
            var options = driver.Options;

            options.GenerateName = GenerateName;

            var module = options.AddModule("FreeCAD");
            module.LibraryName = "FreeCAD";

            var headers = new[]
            {
                "Base/Vector3D.h",
                "App/Document.h",
            };

            module.Headers.AddRange(headers);

            Program.Setup(driver, module, TargetPlatform);

            var parserOptions = driver.ParserOptions;
            parserOptions.UnityBuild = true;
            //parserOptions.SkipLayoutInfo = true;

            options.OutputDir = Path.Combine("gen", GeneratorKind.ToString().ToLowerInvariant());
            //options.GenerateDefaultValuesForArguments = true;
            options.GenerateDeprecatedDeclarations = false;
            options.GenerationOutputMode = GenerationOutputMode.FilePerUnit;
            options.CompileCode = false;
            options.GenerateClassTemplates = true;
            options.GeneratorKind = GeneratorKind;
            options.UseHeaderDirectories = true;
            options.GenerateExternalDataFields = true;
            //options.DryRun = true;
            //options.Verbose = true;
        }

        private string GenerateName(TranslationUnit arg)
        {
            var fileRelativePath = arg.FileRelativeDirectory;
            var elements = fileRelativePath.Split('/');
            var path = Path.Combine(string.Join('/', elements), $"{arg.FileNameWithoutExtension}JS");
            return path;
        }

        public void SetupPasses(Driver driver)
        {
        }

        public void Preprocess(Driver driver, ASTContext ctx)
        {
            var passBuilder = driver.Context.TranslationUnitPasses;
            var options = driver.Options;

            ctx.IgnoreTranslationUnits();

            // Base
            // ----------------------------------------------------------------
            //ctx.GenerateTranslationUnits(new[] {"Base/Vector3D.h"});
            ctx.IgnoreClassWithName("float_traits");

            // App
            // ----------------------------------------------------------------   
            ctx.GenerateTranslationUnits(new[] {"App/Document.h"});
        }

        public void Postprocess(Driver driver, ASTContext ctx)
        {
        }

        public void GenerateCode(Driver driver, List<GeneratorOutput> outputs)
        {
        }
    }

    class ASTHelpers
    {
        public static void MoveTranslationUnitFromTo(ASTContext ctx,
            string source, string dest)
        {
            var sourceUnit = ctx.TranslationUnits.Find(u => u.FileRelativePath == source);
            var destUnit = ctx.TranslationUnits.Find(u => u.FileRelativePath == dest);

            if (sourceUnit == null || destUnit == null)
                throw new Exception("Translation unit was not found");

            MoveTranslationUnitFromTo(ctx, sourceUnit, destUnit);
        }

        public static void MoveTranslationUnitFromTo(ASTContext ctx,
            TranslationUnit source, TranslationUnit dest)
        {
            var pass = new MoveTranslationUnitDecls(source, dest);
            source.Visit(pass);
        }

        public static void MoveDefinitionsFromTo(ASTContext ctx,
            string source, string dest)
        {
            var sourceClass = ctx.FindCompleteClass(source);
            if (sourceClass == null)
                throw new Exception($"Cannot find class {source}");

            var destClass = ctx.FindCompleteClass(dest);
            if (destClass == null)
                throw new Exception($"Cannot find class {dest}");

            MoveDefinitionsFromTo(sourceClass, destClass);
        }

        public static void MoveDefinitionsFromTo(Class source, Class dest)
        {
            source.GenerationKind = GenerationKind.None;

            foreach (var decl in source.Declarations)
            {
                decl.Namespace = dest;
                dest.Declarations.Add(decl);
            }

            foreach (var field in source.Fields)
            {
                field.Namespace = dest;
                dest.Fields.Add(field);
            }

            foreach (var prop in source.Properties)
            {
                var existing = dest.Methods.FirstOrDefault(
                    p => p.Name == prop.Name);
                if (existing != null && existing.IsOverride)
                    continue;

                prop.Namespace = dest;
                dest.Properties.Add(prop);
            }

            foreach (var method in source.Methods)
            {
                if (method.IsDestructor)
                    continue;

                var existing = dest.Methods.Where(m =>
                {
                    if (method.IsConstructor)
                        return m.IsConstructor;

                    return m.Name == method.Name;
                });

                // If a method with the same signature already exists, then bail.
                if (existing.Any(m => m.HasSameSignature(method)))
                    continue;

                /*if (existing != null && method.HasSameSignature(existing))
                {
                    continue;

                    /*if (existing.IsOverride)
                        continue;

                    if (existing.IsVirtual)
                        continue;
                }*/

                method.Namespace = dest;
                dest.Methods.Add(method);
            }

            var baseSpec = dest.Bases.Find(b => b.Class == source);
            if (baseSpec != null)
            {
                baseSpec.ExplicitlyIgnore();

                dest.Bases.AddRange(source.Bases);
            }

            //destClass.Bases.Remove(baseSpec);
        }
    }

    class MoveTranslationUnitDecls : TranslationUnitPass
    {
        readonly TranslationUnit sourceUnit;
        readonly TranslationUnit targetUnit;

        public MoveTranslationUnitDecls(TranslationUnit source, TranslationUnit target)
        {
            sourceUnit = source;
            targetUnit = target;
        }

        public override bool VisitDeclaration(Declaration decl)
        {
            if (decl is TranslationUnit)
                return true;

            if (!(decl.Namespace is Namespace || decl.Namespace is TranslationUnit))
                return false;

            if (decl.TranslationUnit != sourceUnit)
                return false;

            Namespace targetNamespace = targetUnit;
            if (!(decl.Namespace is TranslationUnit))
            {
                // Find same namespace in the target unit.
                // TODO:
                throw new Exception();
            }

            targetNamespace.Declarations.Add(decl);
            decl.Namespace = targetNamespace;

            return true;
        }

        public override bool VisitTranslationUnit(TranslationUnit unit)
        {
            var res = base.VisitTranslationUnit(unit);
            unit.GenerationKind = GenerationKind.None;
            return res;
        }
    }

    class IgnoreMethodWithReferences : TranslationUnitPass
    {
        public override bool VisitMethodDecl(Method method)
        {
            if (!method.IsGenerated)
                return false;

            if (method.ReturnType.Type.IsReference() ||
                method.ReturnType.Type.Desugar().IsReference())
                method.GenerationKind = GenerationKind.None;

            return true;
        }
    }

    class FixEnumsScope : TranslationUnitPass
    {
        public override bool VisitEnumDecl(Enumeration @enum)
        {
            @enum.SetScoped();
            return true;
        }
    }

    class FixMethodOverrides : TranslationUnitPass
    {
        static Class GetBaseClassForOverridenMethod(Method method)
            => method.BaseMethod.Namespace as Class;

        static bool HasGeneratedBaseClass(Class @class, Class baseClass)
        {
            if (@class == baseClass)
                return true;

            foreach (var bs in @class.Bases)
            {
                if (!bs.IsGenerated)
                    continue;

                if (!bs.IsClass || !bs.Class.IsGenerated)
                    continue;

                if (HasGeneratedBaseClass(bs.Class, baseClass))
                    return true;
            }

            return false;
        }

        public static bool FixMethodOverride(Method method)
        {
            if (!method.IsGenerated)
                return false;

            if (!method.IsVirtual || method.IsDestructor)
                return false;

            method.IsOverride = false;

            var @class = method.Namespace as Class;
            var baseMethod = @class.GetBaseMethod(method);

            if (baseMethod != null)
            {
                var baseClass = baseMethod.Namespace as Class;
                method.IsOverride = baseClass?.IsGenerated ?? false;
            }

            return true;
        }

        public override bool VisitMethodDecl(Method method)
        {
            if (!VisitDeclaration(method))
                return false;

            return FixMethodOverride(method);
        }
    }

    public static class StringExtensions
    {
        /// <summary>
        /// Compares the string against a given pattern.
        /// </summary>
        /// <param name="str">The string.</param>
        /// <param name="pattern">The pattern to match, where "*" means any
        /// sequence of characters, and "?" means any single character.</param>
        /// <returns><c>true</c> if the string matches the given pattern;
        /// otherwise <c>false</c>.
        /// </returns>
        public static bool Match(this string str, string pattern)
        {
            return new Regex(
                "^" + Regex.Escape(pattern).Replace(@"\*", ".*").Replace(@"\?", ".") + "$",
                RegexOptions.IgnoreCase | RegexOptions.Singleline
            ).IsMatch(str);
        }
    }
}