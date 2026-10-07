-- test template for The0x539's KaraTemplater (engine 0x539)

--@meta engine=0x539 style=JP

--@code once | 配置
C1 = '&H0000FF&'
C2 = '&HFF0000&'
function is_long() return syl.duration >= 500 end

--@template line | 整句
{\an8\fad(200,200)}

--@mixin char
{\3c!util.gbc(C1, C2)!}

--@template syl noblank notext loop spark 2 layer=2 | 闪光
!retime("syl", 0, 300)!{\an5\pos(!util.ftoa(orgline.left + syl.center)!,!util.ftoa(orgline.middle)!)\p1}m 0 0 l $loop_spark 0 l 0 $loop_spark

--@template syl noblank if is_long layer=3 | 长音
!retime("presyl2postline")!{\an5\pos(!util.ftoa(orgline.left + syl.center)!,!util.ftoa(orgline.middle)!)\t(\fscx150)}

--@template word anystyle notext layer=4 | 逐词
{\word!word.wi!}
