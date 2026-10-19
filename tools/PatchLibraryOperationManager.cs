// LibraryCanvasManager.InitData 的空指针修复（Unity 程序集 Assembly-CSharp.dll）。
//
// 真机日志（com.huawei.vrlauncherx）：
//     E/Unity: NullReferenceException: Object reference not set to an instance of an object
//       at LibraryCanvasManager.InitData ()
//       at LibraryCanvasManager.Start ()
//
// 反编译 IL 可见 InitData 一开头就：
//     LibraryDataManager.GetInstance() -> this.mLibDataManager
//     this.mLibOperationManager.SetOperationState(...)     <-- callvirt 在 null 上
// 而 mLibOperationManager 是 Unity 序列化字段（Inspector 引用），
// LibraryCanvasManager 自己从头到尾没有任何一处给它赋值；Unity 的 Start 顺序
// 又不保证引用的那个组件已经就绪，于是 InitData 拿到 null。
// 旧仓 porting/original-patches/desktop/PatchDesktop.cs 修的是同一类问题
// （LibrarySortPanel 的 mCurrentCardDatas 未初始化）。
//
// 修法：在 InitData 开头插入一小段「序列化字段为空时取单例」的兜底：
//     if (this.mLibOperationManager == null)
//         this.mLibOperationManager = LibraryOperationManager.get_Instance();
// 只动这一个方法的前 6 条 IL，其余原样。
using System;
using System.Linq;
using Mono.Cecil;
using Mono.Cecil.Cil;

static class PatchLibraryOperationManager
{
    static int Main(string[] args)
    {
        if (args.Length != 1)
        {
            Console.Error.WriteLine("usage: PatchLibraryOperationManager <Assembly-CSharp.dll>");
            return 2;
        }
        var resolver = new DefaultAssemblyResolver();
        resolver.AddSearchDirectory(System.IO.Path.GetDirectoryName(args[0]));
        using (var module = ModuleDefinition.ReadModule(
            args[0], new ReaderParameters { AssemblyResolver = resolver, InMemory = true }))
        {
            var type = module.GetType("LibraryCanvasManager");
            if (type == null) { Console.Error.WriteLine("LibraryCanvasManager not found"); return 1; }
            var initData = type.Methods.SingleOrDefault(m => m.Name == "InitData");
            if (initData == null || !initData.HasBody)
            {
                Console.Error.WriteLine("LibraryCanvasManager.InitData not found");
                return 1;
            }
            var field = type.Fields.SingleOrDefault(f => f.Name == "mLibOperationManager");
            if (field == null) { Console.Error.WriteLine("mLibOperationManager not found"); return 1; }
            var manager = module.GetType("LibraryOperationManager");
            var getter = manager == null
                ? null : manager.Methods.SingleOrDefault(m => m.Name == "get_Instance");
            if (getter == null)
            {
                Console.Error.WriteLine("LibraryOperationManager.get_Instance not found");
                return 1;
            }

            var instructions = initData.Body.Instructions;
            bool initDataPatched = !(instructions.Count > 0 &&
                instructions[0].OpCode == OpCodes.Ldarg_0 && instructions[1].OpCode == OpCodes.Ldfld &&
                instructions[2].OpCode == OpCodes.Brtrue);
            if (!initDataPatched)
            {
                Console.WriteLine("InitData already patched (skip)");
            }
            else
            {
                var il = initData.Body.GetILProcessor();
                var first = instructions[0];
                il.InsertBefore(first, Instruction.Create(OpCodes.Ldarg_0));
                il.InsertBefore(first, Instruction.Create(OpCodes.Ldfld, field));
                il.InsertBefore(first, Instruction.Create(OpCodes.Brtrue, first));
                il.InsertBefore(first, Instruction.Create(OpCodes.Ldarg_0));
                il.InsertBefore(first, Instruction.Create(OpCodes.Call, getter));
                il.InsertBefore(first, Instruction.Create(OpCodes.Stfld, field));
                Console.WriteLine("patched: LibraryCanvasManager.InitData -> fallback to LibraryOperationManager.Instance");
            }

            PatchSortPanel(module);
            module.Write(args[0]);
        }
        return 0;
    }

    // 旧仓 porting/original-patches/desktop/PatchDesktop.cs 修过的同一处：
    // Unity 不保证不同组件 Start 的顺序，LibraryCanvasManager.InitData 会先读
    // LibrarySortPanel.CurrentCardDatas，而那个 List 要到 LibrarySortPanel.Start
    // 才被填充 —— 于是 InitData 里 .Count 直接空指针。
    // 修法：在 LibrarySortPanel 的构造函数里就把 List 建好，后面的原有逻辑照常填充。
    static void PatchSortPanel(ModuleDefinition module)
    {
        var type = module.GetType("LibrarySortPanel");
        if (type == null) { Console.Error.WriteLine("LibrarySortPanel not found (skip)"); return; }
        var field = type.Fields.SingleOrDefault(f => f.Name == "mCurrentCardDatas");
        if (field == null) { Console.Error.WriteLine("mCurrentCardDatas not found (skip)"); return; }
        var ctor = type.Methods.SingleOrDefault(m => m.Name == ".ctor");
        if (ctor == null || !ctor.HasBody) { Console.Error.WriteLine("LibrarySortPanel..ctor not found (skip)"); return; }

        var instructions = ctor.Body.Instructions;
        bool already = false;
        foreach (var instruction in instructions)
        {
            var reference = instruction.Operand as MethodReference;
            if (instruction.OpCode == OpCodes.Newobj && reference != null &&
                reference.Name == ".ctor" &&
                reference.DeclaringType.FullName == "System.Collections.Generic.List`1<CardData>")
            {
                already = true;
                break;
            }
        }
        if (already)
        {
            Console.Error.WriteLine("LibrarySortPanel..ctor already initializes mCurrentCardDatas");
            return;
        }
        // 复用模块里已有的 List<CardData>..ctor 引用，避免自己拼泛型签名出错
        MethodReference listCtorRef = null;
        foreach (var type2 in module.Types)
        foreach (var method2 in type2.Methods)
        {
            if (!method2.HasBody) continue;
            foreach (var instruction in method2.Body.Instructions)
            {
                if (instruction.OpCode != OpCodes.Newobj) continue;
                var candidate = instruction.Operand as MethodReference;
                if (candidate != null && candidate.Name == ".ctor" &&
                    candidate.DeclaringType.FullName ==
                    "System.Collections.Generic.List`1<CardData>")
                {
                    listCtorRef = candidate;
                    break;
                }
            }
            if (listCtorRef != null) break;
        }
        if (listCtorRef == null)
        {
            Console.Error.WriteLine("List<CardData>..ctor reference not found (skip)");
            return;
        }
        var il = ctor.Body.GetILProcessor();
        var first = instructions[0];
        il.InsertBefore(first, Instruction.Create(OpCodes.Ldarg_0));
        il.InsertBefore(first, Instruction.Create(OpCodes.Newobj, listCtorRef));
        il.InsertBefore(first, Instruction.Create(OpCodes.Stfld, field));
        Console.WriteLine("patched: LibrarySortPanel..ctor -> mCurrentCardDatas = new List<CardData>()");
    }
}
