; ModuleID = 'programs.e3389e8931ddf310-cgu.0'
source_filename = "programs.e3389e8931ddf310-cgu.0"
target datalayout = "e-m:o-p270:32:32-p271:32:32-p272:64:64-i64:64-i128:128-n32:64-S128-Fn32"
target triple = "arm64-apple-macosx11.0.0"

; Function Attrs: mustprogress nofree norecurse nosync nounwind willreturn memory(none)
define noundef i32 @rust_max(i32 noundef %a, i32 noundef %b) unnamed_addr #0 {
start:
  %a.b = tail call i32 @llvm.smax.i32(i32 %a, i32 %b)
  ret i32 %a.b
}

; Function Attrs: mustprogress nofree norecurse nosync nounwind willreturn memory(none)
define noundef i64 @rust_mix(i64 noundef %a, i64 noundef %b) unnamed_addr #0 {
start:
  %_0.i = add i64 %b, %a
  %0 = tail call noundef i64 @llvm.fshl.i64(i64 %_0.i, i64 %_0.i, i64 7)
  %_0 = xor i64 %0, %b
  ret i64 %_0
}

; Function Attrs: mustprogress nocallback nofree nosync nounwind speculatable willreturn memory(none)
declare i64 @llvm.fshl.i64(i64, i64, i64) #1

; Function Attrs: nocallback nofree nosync nounwind speculatable willreturn memory(none)
declare i32 @llvm.smax.i32(i32, i32) #2

attributes #0 = { mustprogress nofree norecurse nosync nounwind willreturn memory(none) "frame-pointer"="non-leaf" "probe-stack"="inline-asm" "target-cpu"="apple-m1" }
attributes #1 = { mustprogress nocallback nofree nosync nounwind speculatable willreturn memory(none) }
attributes #2 = { nocallback nofree nosync nounwind speculatable willreturn memory(none) }

!llvm.module.flags = !{!0}
!llvm.ident = !{!1}

!0 = !{i32 8, !"PIC Level", i32 2}
!1 = !{!"rustc version 1.90.0 (1159e78c4 2025-09-14)"}
