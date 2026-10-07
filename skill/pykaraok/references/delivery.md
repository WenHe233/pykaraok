# 交付规范

## 文件

- **不覆盖**用户的原文件和以前交付的版本。新版本按改动内容加后缀，例如 `歌词_特效.ass`、`歌词_特效_v2.ass`、`歌词_特效_水彩常驻.ass`、`歌词_特效_繁体.ass`。
- 默认交付**单文件**，包含三部分：
  - 说明行和模板行；
  - karaoke 注释行，即原歌词，文字和标签不改；
  - 生成的 fx 行。

  用户打开后可以直接在 Aegisub 里改参数、重新套用。用户要求时再拆分成 `X_template.ass` 和 `X_fx.ass`。
- 模板源文件（`*.fx.lua`）和交付文件放在一起，方便下次修改。
- 原文件里的 BOM、换行、`[Aegisub Project Garbage]`、Extradata、未改动的行保持原样（pykaraok 会自动处理）。

## 预览

```bash
pykaraok render preview 歌词_特效.ass -o 预览.mp4
```

- 只压歌曲区间（默认取 fx 行的时间范围前后各 2 秒），带音频，H.264，默认约 4.5 Mbps。整段 1080p 预览一般在 30 到 100 MB。
- 用户要更小的文件时，加 `--width 1280` 或调低 `--bitrate`。

## 交付前

1. `pykaraok check 交付.ass --reapply` 没有 error 和 warn，jumps 为 0。
2. `render lines` 把全部句子看过一遍。
3. 繁体版重复以上步骤。

## 给用户的说明（每次都写）

- 用到的字体，以及“在 Aegisub 里重新套用前要先安装这些字体，Aegisub 按系统字体计算字宽”。
- 只保证 libass 下的效果；在 Aegisub 里要把视频预览切到 libass 才能看到正确效果。
- 参数在哪一行 code once 里，改什么会怎样。
- 用到了 Yutils、ILL 或 0x539 模板器时，要写明用户需要安装什么。
- 改动了哪些内容，旧版本放在哪里。
