// 原版 HVRInputModule.UpdateAnchorPos 的空指针缺陷修复（Unity 程序集 Assembly-CSharp.dll）。
//
// 原始 C# 意图：
//     var nowGaze  = pointer.m_NowGazeObj;
//     var lastGaze = pointer.m_LastGazeObj;
//     if (nowGaze == lastGaze) {                       // 同一目标，或都为 null
//         if (nowGaze != null) pointer.OnLineHover(pos, true);
//         if (lastGaze.ToString().Equals("null"))      // <-- 对 Unity 伪 null 解引用
//             pointer.OnLineExit(pos, false);
//     }
// 在通用安卓上没有注视指针兜底，lastGaze 为 null 时这句必抛
// NullReferenceException（被外层 try/catch 吞掉并打日志），后果是 OnLineExit
// 被跳过：射线离开按钮后 hover 状态留在旧目标上，下次再瞄同一个按钮只走
// OnLineHover、不再走 OnLineEnter —— 表现为「射线偶尔点不中画面里的按钮」。
//
// 修法只改这一处判断：lastGaze.ToString().Equals("null")  ->  lastGaze == null
// （UnityEngine.Object::op_Equality，对伪 null 安全）。同一处理在旧仓
// porting/original-patches/desktop/PatchDesktop.cs 的 NULL POINTER GUARD 里
// 已经真机验证过。脚本对原始 IL 形态做断言，形态变化即报错停止。
using System;
using System.Linq;
using Mono.Cecil;
using Mono.Cecil.Cil;

static class PatchUnityPointerNullGuard
{
    static int Main(string[] args)
    {
        if (args.Length != 1)
        {
            Console.Error.WriteLine("usage: PatchUnityPointerNullGuard <Assembly-CSharp.dll>");
            return 2;
        }
        var resolver = new DefaultAssemblyResolver();
        resolver.AddSearchDirectory(System.IO.Path.GetDirectoryName(args[0]));
        using (var module = ModuleDefinition.ReadModule(
            args[0], new ReaderParameters { AssemblyResolver = resolver, InMemory = true }))
        {
            var type = module.GetType("HVRInputModule");
            if (type == null) { Console.Error.WriteLine("HVRInputModule not found"); return 1; }
            var method = type.Methods.SingleOrDefault(m => m.Name == "UpdateAnchorPos");
            if (method == null || !method.HasBody)
            {
                Console.Error.WriteLine("HVRInputModule.UpdateAnchorPos not found");
                return 1;
            }

            var instructions = method.Body.Instructions;
            var candidates = instructions.Where(i =>
                i.OpCode == OpCodes.Callvirt &&
                i.Operand is MethodReference && ((MethodReference)i.Operand).Name == "ToString" &&
                i.Next.OpCode == OpCodes.Ldstr && (string)i.Next.Operand == "null").ToList();
            if (candidates.Count != 1)
            {
                Console.Error.WriteLine(
                    "expected exactly one ToString-null site, found {0} (already patched or IL changed)",
                    candidates.Count);
                return 1;
            }
            var equality = instructions
                .Select(i => i.Operand as MethodReference)
                .FirstOrDefault(m => m != null && m.Name == "op_Equality" &&
                                     m.DeclaringType.FullName == "UnityEngine.Object");
            if (equality == null)
            {
                Console.Error.WriteLine("UnityEngine.Object::op_Equality not found");
                return 1;
            }

            var toString = candidates[0];
            Console.WriteLine("before: {0} | {1} | {2}", toString, toString.Next, toString.Next.Next);
            toString.OpCode = OpCodes.Ldnull;
            toString.Operand = null;
            toString.Next.OpCode = OpCodes.Call;
            toString.Next.Operand = equality;
            toString.Next.Next.OpCode = OpCodes.Nop;
            toString.Next.Next.Operand = null;
            Console.WriteLine("after:  {0} | {1} | {2}", toString, toString.Next, toString.Next.Next);

            module.Write(args[0]);
            Console.WriteLine("patched: HVRInputModule.UpdateAnchorPos null guard");
        }
        return 0;
    }
}
