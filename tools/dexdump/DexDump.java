/*
 * 只读反汇编入口：把 apktool 自带 dexlib2/baksmali 的 CLI 重新接出来。
 *
 * 为什么需要它：EMUI 9 的 /system/framework/vr.jar 是 200 字节的剥离壳，
 * 真正的 dex 以 compact dex（cdex001）形式放在 vr.vdex 里；官方 baksmali
 * 2.2.7 与 jadx 0.9 都不认这种形态，而 apktool 2.10 自带的 dexlib2 认
 * （OatFile$OatCDexFile / CDexBackedMethodImplementation）。apktool 把
 * CLI 入口 Main 抽成了 abstract，只留下 Baksmali.disassembleDexFile，
 * 所以这里用十几行把它重新调起来。
 *
 * 用法：
 *   javac -encoding UTF-8 -cp tools/apktool_2.10.0.jar -d build/dexdump tools/dexdump/DexDump.java
 *   java -cp "tools/apktool_2.10.0.jar;build/dexdump" DexDump <输入> <输出目录> [api]
 *   java -cp "tools/apktool_2.10.0.jar;build/dexdump" DexDump --list <输入> [api]
 *   java -cp "tools/apktool_2.10.0.jar;build/dexdump" DexDump --methods <输入> [api]
 *
 * 输入可以是 oat/odex（同目录需要放对应的 *.vdex），也可以是单独的 cdex。
 * --list 只打印类描述符，用于把原包/原厂固件里的类名做成索引（不落盘 smali）。
 */
import com.android.tools.smali.baksmali.Baksmali;
import com.android.tools.smali.baksmali.BaksmaliOptions;
import com.android.tools.smali.dexlib2.DexFileFactory;
import com.android.tools.smali.dexlib2.Opcodes;
import com.android.tools.smali.dexlib2.dexbacked.DexBackedDexFile;
import com.android.tools.smali.dexlib2.iface.ClassDef;
import com.android.tools.smali.dexlib2.iface.MultiDexContainer;

import java.io.File;
import java.util.TreeSet;

public final class DexDump {
    public static void main(String[] args) throws Exception {
        if (args.length < 2) {
            System.err.println("用法：DexDump <输入 odex/vdex/cdex/apk/jar> <输出目录> [api]");
            System.err.println("     DexDump --list <输入> [api]");
            System.exit(2);
        }
        boolean listOnly = "--list".equals(args[0]) || "--methods".equals(args[0]);
        boolean withMethods = "--methods".equals(args[0]);
        File input = new File(args[listOnly ? 1 : 0]);
        File output = listOnly ? null : new File(args[1]);
        // 两种调用的第 3 个参数都是 api（可选）
        int api = args.length > 2 ? Integer.parseInt(args[2]) : 29;
        if (output != null) {
            output.mkdirs();
        }

        MultiDexContainer container = DexFileFactory.loadDexContainer(input, new Opcodes(api, 0));
        int dumped = 0;
        for (Object raw : container.getDexEntryNames()) {
            String name = (String) raw;
            DexBackedDexFile dex = container.getEntry(name).getDexFile();
            if (listOnly) {
                TreeSet<String> classes = new TreeSet<>();
                // classSection 是 AbstractList 的子类（apktool 精简过 dexlib2，没有公开的 DexFile 接口）
                for (Object item : dex.classSection) {
                    ClassDef classDef = (ClassDef) item;
                    if (!withMethods) {
                        classes.add(classDef.getType());
                        continue;
                    }
                    for (Object group : new Object[] {
                            classDef.getDirectMethods(), classDef.getVirtualMethods() }) {
                        for (Object method : (Iterable<?>) group) {
                            com.android.tools.smali.dexlib2.iface.Method m =
                                    (com.android.tools.smali.dexlib2.iface.Method) method;
                            StringBuilder parameters = new StringBuilder();
                            for (Object parameter : m.getParameters()) {
                                parameters.append(parameter);
                            }
                            classes.add(classDef.getType() + "->" + m.getName()
                                    + "(" + parameters + ")" + m.getReturnType());
                        }
                    }
                }
                for (String type : classes) {
                    System.out.println(type);
                }
            } else {
                File target = new File(output, name.replace('/', '_').replace(".dex", ""));
                BaksmaliOptions options = new BaksmaliOptions();
                Baksmali.disassembleDexFile(dex, target, 1, options);
                System.out.println("已反汇编 " + name + " -> " + target);
            }
            dumped++;
        }
        if (!listOnly) {
            System.out.println("共 " + dumped + " 个 dex");
        }
    }
}
