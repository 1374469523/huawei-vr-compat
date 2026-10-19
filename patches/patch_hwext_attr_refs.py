"""把布局里指向 EMUI 扩展资源包（`androidhwext`，资源包 id `0x02`）的
`?attr` 引用，换成它在原厂固件里的真实取值。

为什么必须换：`?0x0201xxxx` 是 **共享库属性**（编译成
`Res_value::TYPE_DYNAMIC_ATTRIBUTE = 0x8`，属性 id 属于资源包 `0x02`）。
EMUI 上 `framework-res-hwext.apk` 以共享库身份加载，主题里有这些属性的值，
引用就解析成具体尺寸/字体；通用安卓没有这个包，**主题查不到，0x8 原样透传**，
于是三星的 `TextView.readTextAppearance()` 拿到一个转换不了的 0x8：

    java.lang.UnsupportedOperationException:
        Can't convert value at index 2 to dimension: type=0x8
      at android.widget.TextView.readTextAppearance(TextView.java:4712)

值不是猜的。下面是 HMA-AL00 EMUI 11.0.0.155 整包里
`/system/framework/framework-res-hwext.apk`（21639272 字节，
`aapt2 dump resources` 结果见 docs/evidence/emui-hwext-attrs-2026-09-16.md）
的原始条目：`androidhwext:Theme.Emui` 里每个属性指向的 dimen/string，
再取那些 dimen/string 的默认配置值。布局、元素、文案、其它属性一律不动，
只把「指向平台包的那一个值」换成平台原本会给出的那个值。

唯一的例外是 `0x02010013`（`buttonStyleEmphasize`）：它指向的是**整套样式**
（含 `androidhwext` 自己的九宫格背景 `@drawable/btn_emphasize_emui_translucent`），
没法内联成一个属性值，本脚本不碰它，行为与引用解析不到时一致（走应用主题
默认按钮样式），台账里另行记录。

用法：python patches/patch_hwext_attr_refs.py <解码树或 -a 全部>
"""

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from axml_edit import BinaryXml, RES_XML_START_ELEMENT_TYPE  # noqa: E402

REPO = HERE.parent

UNTOUCHED = 0x02010013  # buttonStyleEmphasize：整套样式，见文件头说明

# 属性 id -> (类型, 值, 原厂条目)
#   dimen：COMPLEX_UNIT_DIP=1 / COMPLEX_UNIT_SP=2
TYPE_DIMENSION = 0x05
UNIT_DIP = 1
UNIT_SP = 2
TYPE_STRING = 0x03

ATTRS = {
    0x020100c8: (TYPE_DIMENSION, 24, UNIT_DIP,
                 "maxPaddingStart -> @dimen/emui_dimens_max_start = 24dp"),
    0x020100ca: (TYPE_DIMENSION, 24, UNIT_DIP,
                 "maxPaddingEnd -> @dimen/emui_dimens_max_end = 24dp"),
    0x020100cd: (TYPE_DIMENSION, 24, UNIT_DIP,
                 "defaultPaddingBottomFixed -> @dimen/emui_dimens_default_bottom_fixed = 24dp"),
    0x020100da: (TYPE_DIMENSION, 16, UNIT_DIP,
                 "elementsMarginHorizontalL -> @dimen/emui_dimens_element_horizontal_large = 16dp"),
    0x020100e8: (TYPE_DIMENSION, 16, UNIT_SP,
                 "textSizeBody1 -> @dimen/emui_text_size_body1 = 16sp"),
    0x020100e9: (TYPE_DIMENSION, 14, UNIT_SP,
                 "textSizeBody2 -> @dimen/emui_text_size_body2 = 14sp"),
    0x020100ea: (TYPE_DIMENSION, 12, UNIT_SP,
                 "textSizeBody3 -> @dimen/emui_text_size_body3 = 12sp"),
    0x020100eb: (TYPE_DIMENSION, 10, UNIT_DIP,
                 "textSizeCaption -> @dimen/emui_text_size_caption = 10dp"),
    0x020100e1: (TYPE_DIMENSION, 30, UNIT_SP,
                 "textSizeHeadline6 -> @dimen/emui_text_size_headline6 = 30sp"),
    0x020100e2: (TYPE_DIMENSION, 20, UNIT_SP,
                 "textSizeHeadline7 -> @dimen/emui_text_size_headline7 = 20sp"),
    0x020100e4: (TYPE_DIMENSION, 16, UNIT_SP,
                 "textSizeSubTitle2 -> @dimen/emui_text_size_subtitle2 = 16sp"),
    0x020100e5: (TYPE_DIMENSION, 14, UNIT_SP,
                 "textSizeSubTitle3 -> @dimen/emui_text_size_subtitle3 = 14sp"),
    # 字体族名换成通用安卓里语义相同的那一族：
    #   androidhwext:textFontFamilyRegular = "sans-serif"（本来就是 AOSP 名）
    #   androidhwext:textFontFamilyMedium  = "HwChinese-medium"（华为自带字体，
    #   通用安卓没有这个族名 -> 会退回常规字重；语义等价的是 sans-serif-medium）
    0x020100ef: (TYPE_STRING, "sans-serif",
                 "textFontFamilyRegular -> @string/emui_text_font_family_regular"),
    0x020100f0: (TYPE_STRING, "sans-serif-medium",
                 "textFontFamilyMedium -> @string/emui_text_font_family_medium = HwChinese-medium"),
}

# 每个文件里应改的处数（改前改后都要对上，防止原包换了之后脚本默默不动）
EXPECTED = {
    "res/layout/activity_install.xml": 13,
    "res/layout/activity_service_term.xml": 14,
    "res/layout/activity_welcome.xml": 4,
    "res/layout/apk_item.xml": 1,
    "res/layout/fragment_ui_cable_detail_panels.xml": 18,
    "res/layout/layout_permission_item.xml": 4,
    "res/layout/layout_permission_notice.xml": 9,
}


def complex_dimension(value, unit):
    """COMPLEX_RADIX_23p0（整数）编码：mantissa << 8 | radix << 4 | unit。"""
    return (value << 8) | (0 << 4) | unit


def patch_file(path):
    data = path.read_bytes()
    xml = BinaryXml(data)
    changed = 0
    for ctype, payload in xml.entries:
        if ctype != RES_XML_START_ELEMENT_TYPE:
            continue
        attributes = []
        for attr in payload.attributes:
            ns, aname, raw, size, res0, dtype, value = attr
            if dtype == 0x08 and value in ATTRS:  # TYPE_DYNAMIC_ATTRIBUTE
                spec = ATTRS[value]
                if spec[0] == TYPE_DIMENSION:
                    attr = (ns, aname, raw, size, res0, TYPE_DIMENSION,
                            complex_dimension(spec[1], spec[2]))
                else:
                    index = xml.pool.add(spec[1])
                    attr = (ns, aname, index, size, res0, TYPE_STRING, index)
                changed += 1
            attributes.append(attr)
        payload.attributes = attributes
    if changed:
        path.write_bytes(xml.build())
    return changed


def count_remaining(path):
    xml = BinaryXml(path.read_bytes())
    return [(xml.pool.strings[payload.name_index],
             xml.pool.strings[attr[1]], attr[6])
            for ctype, payload in xml.entries
            if ctype == RES_XML_START_ELEMENT_TYPE
            for attr in payload.attributes
            if attr[5] in (0x02, 0x08) and (attr[6] >> 24) == 0x02]


def run(tree):
    failures = []
    total = 0
    for relative, expected in EXPECTED.items():
        path = Path(tree) / relative
        if not path.exists():
            failures.append(f"缺少文件：{relative}")
            continue
        changed = patch_file(path)
        total += changed
        if changed != expected:
            failures.append(f"{relative}: 改了 {changed} 处，期望 {expected} 处")
            continue
        left = count_remaining(path)
        bad = [item for item in left if item[2] != UNTOUCHED]
        if bad:
            failures.append(f"{relative}: 仍有未内联的 hwext 属性 {bad}")
        print(f"  {relative}: {changed} 处"
              f"（保留 {len(left)} 处 buttonStyleEmphasize）")
    return total, failures


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    trees = ([REPO / "decode" / name for name in sorted(
        p.name for p in (REPO / "decode").iterdir() if p.is_dir())]
        if sys.argv[1] == "-a" else [Path(sys.argv[1])])

    total = 0
    failures = []
    for tree in trees:
        if not (Path(tree) / "res/layout/activity_service_term.xml").exists():
            continue
        print(f"== {Path(tree).name}")
        count, problems = run(tree)
        total += count
        failures.extend(problems)
    print(f"合计内联 {total} 处")
    for problem in failures:
        print(f"FAIL {problem}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
