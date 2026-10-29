; ModuleID = 'languages/llvm/examples/programs.c'
source_filename = "languages/llvm/examples/programs.c"
target datalayout = "e-m:o-i64:64-i128:128-n32:64-S128-Fn32"
target triple = "arm64-apple-macosx15.0.0"

; Function Attrs: noinline nounwind optnone ssp uwtable(sync)
define i32 @max(i32 noundef %0, i32 noundef %1) #0 {
  %3 = alloca i32, align 4
  %4 = alloca i32, align 4
  store i32 %0, ptr %3, align 4
  store i32 %1, ptr %4, align 4
  %5 = load i32, ptr %3, align 4
  %6 = load i32, ptr %4, align 4
  %7 = icmp sgt i32 %5, %6
  br i1 %7, label %8, label %10

8:                                                ; preds = %2
  %9 = load i32, ptr %3, align 4
  br label %12

10:                                               ; preds = %2
  %11 = load i32, ptr %4, align 4
  br label %12

12:                                               ; preds = %10, %8
  %13 = phi i32 [ %9, %8 ], [ %11, %10 ]
  ret i32 %13
}

; Function Attrs: noinline nounwind optnone ssp uwtable(sync)
define i32 @mix(i32 noundef %0, i32 noundef %1) #0 {
  %3 = alloca i32, align 4
  %4 = alloca i32, align 4
  store i32 %0, ptr %3, align 4
  store i32 %1, ptr %4, align 4
  %5 = load i32, ptr %3, align 4
  %6 = load i32, ptr %4, align 4
  %7 = add i32 %5, %6
  %8 = load i32, ptr %3, align 4
  %9 = lshr i32 %8, 3
  %10 = xor i32 %7, %9
  %11 = mul i32 %10, 3
  ret i32 %11
}

; Function Attrs: noinline nounwind optnone ssp uwtable(sync)
define i32 @sum_loop(i32 noundef %0) #0 {
  %2 = alloca i32, align 4
  %3 = alloca i32, align 4
  %4 = alloca i32, align 4
  store i32 %0, ptr %2, align 4
  store i32 0, ptr %3, align 4
  store i32 0, ptr %4, align 4
  br label %5

5:                                                ; preds = %13, %1
  %6 = load i32, ptr %4, align 4
  %7 = load i32, ptr %2, align 4
  %8 = icmp ult i32 %6, %7
  br i1 %8, label %9, label %16

9:                                                ; preds = %5
  %10 = load i32, ptr %4, align 4
  %11 = load i32, ptr %3, align 4
  %12 = add i32 %11, %10
  store i32 %12, ptr %3, align 4
  br label %13

13:                                               ; preds = %9
  %14 = load i32, ptr %4, align 4
  %15 = add i32 %14, 1
  store i32 %15, ptr %4, align 4
  br label %5, !llvm.loop !6

16:                                               ; preds = %5
  %17 = load i32, ptr %3, align 4
  ret i32 %17
}

; Function Attrs: noinline nounwind optnone ssp uwtable(sync)
define i32 @indexed(i32 noundef %0, i32 noundef %1) #0 {
  %3 = alloca i32, align 4
  %4 = alloca i32, align 4
  %5 = alloca [4 x i32], align 4
  store i32 %0, ptr %3, align 4
  store i32 %1, ptr %4, align 4
  %6 = getelementptr inbounds [4 x i32], ptr %5, i64 0, i64 0
  store i32 3, ptr %6, align 4
  %7 = getelementptr inbounds [4 x i32], ptr %5, i64 0, i64 1
  store i32 5, ptr %7, align 4
  %8 = getelementptr inbounds [4 x i32], ptr %5, i64 0, i64 2
  store i32 7, ptr %8, align 4
  %9 = getelementptr inbounds [4 x i32], ptr %5, i64 0, i64 3
  store i32 11, ptr %9, align 4
  %10 = load i32, ptr %4, align 4
  %11 = load i32, ptr %3, align 4
  %12 = and i32 %11, 3
  %13 = zext i32 %12 to i64
  %14 = getelementptr inbounds [4 x i32], ptr %5, i64 0, i64 %13
  store i32 %10, ptr %14, align 4
  %15 = load i32, ptr %3, align 4
  %16 = add i32 %15, 1
  %17 = and i32 %16, 3
  %18 = zext i32 %17 to i64
  %19 = getelementptr inbounds [4 x i32], ptr %5, i64 0, i64 %18
  %20 = load i32, ptr %19, align 4
  %21 = load i32, ptr %3, align 4
  %22 = and i32 %21, 3
  %23 = zext i32 %22 to i64
  %24 = getelementptr inbounds [4 x i32], ptr %5, i64 0, i64 %23
  %25 = load i32, ptr %24, align 4
  %26 = add i32 %20, %25
  ret i32 %26
}

attributes #0 = { noinline nounwind optnone ssp uwtable(sync) "frame-pointer"="non-leaf" "no-trapping-math"="true" "probe-stack"="__chkstk_darwin" "stack-protector-buffer-size"="8" "target-cpu"="apple-m1" "target-features"="+aes,+altnzcv,+bti,+ccdp,+ccidx,+complxnum,+crc,+dit,+dotprod,+flagm,+fp-armv8,+fp16fml,+fptoint,+fullfp16,+jsconv,+lse,+neon,+pauth,+perfmon,+predres,+ras,+rcpc,+rdm,+sb,+sha2,+sha3,+specrestrict,+ssbs,+v8.1a,+v8.2a,+v8.3a,+v8.4a,+v8.5a,+v8a,+zcm,+zcz" }

!llvm.module.flags = !{!0, !1, !2, !3, !4}
!llvm.ident = !{!5}

!0 = !{i32 2, !"SDK Version", [2 x i32] [i32 26, i32 2]}
!1 = !{i32 1, !"wchar_size", i32 4}
!2 = !{i32 8, !"PIC Level", i32 2}
!3 = !{i32 7, !"uwtable", i32 1}
!4 = !{i32 7, !"frame-pointer", i32 1}
!5 = !{!"Apple clang version 17.0.0 (clang-1700.6.4.2)"}
!6 = distinct !{!6, !7}
!7 = !{!"llvm.loop.mustprogress"}
