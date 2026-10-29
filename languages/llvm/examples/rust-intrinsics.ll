; ModuleID = 'intrinsics.2af621cd7c5b3b4d-cgu.0'
source_filename = "intrinsics.2af621cd7c5b3b4d-cgu.0"
target datalayout = "e-m:o-p270:32:32-p271:32:32-p272:64:64-i64:64-i128:128-n32:64-S128-Fn32"
target triple = "arm64-apple-macosx11.0.0"

@_ZN10intrinsics7WEIGHTS17hd1b3e6fd9b1db3b3E = internal unnamed_addr constant [16 x i8] c"\03\00\00\00\05\00\00\00\07\00\00\00\0B\00\00\00", align 4

; Function Attrs: mustprogress nofree norecurse nosync nounwind willreturn memory(none)
define noundef i32 @rust_lookup(i32 noundef %index) unnamed_addr #0 {
start:
  %_4 = and i32 %index, 3
  %_3 = zext nneg i32 %_4 to i64
  %0 = getelementptr inbounds nuw i32, ptr @_ZN10intrinsics7WEIGHTS17hd1b3e6fd9b1db3b3E, i64 %_3
  %_0 = load i32, ptr %0, align 4, !noundef !2
  ret i32 %_0
}

; Function Attrs: mustprogress nofree norecurse nosync nounwind willreturn memory(none)
define noundef range(i64 0, 8589934592) i64 @rust_checked_add(i32 noundef %a, i32 noundef %b) unnamed_addr #0 {
start:
  %0 = tail call { i32, i1 } @llvm.uadd.with.overflow.i32(i32 %a, i32 %b)
  %_5.0 = extractvalue { i32, i1 } %0, 0
  %_5.1 = extractvalue { i32, i1 } %0, 1
  %_6 = zext i32 %_5.0 to i64
  %_7 = select i1 %_5.1, i64 4294967296, i64 0
  %_0 = or disjoint i64 %_7, %_6
  ret i64 %_0
}

; Function Attrs: mustprogress nofree norecurse nosync nounwind willreturn memory(none)
define noundef range(i64 0, 8589934592) i64 @rust_checked_multiply(i32 noundef %a, i32 noundef %b) unnamed_addr #0 {
start:
  %0 = tail call { i32, i1 } @llvm.smul.with.overflow.i32(i32 %a, i32 %b)
  %_5.0 = extractvalue { i32, i1 } %0, 0
  %_5.1 = extractvalue { i32, i1 } %0, 1
  %_6 = zext i32 %_5.0 to i64
  %_8 = select i1 %_5.1, i64 4294967296, i64 0
  %_0 = or disjoint i64 %_8, %_6
  ret i64 %_0
}

; Function Attrs: mustprogress nocallback nofree nosync nounwind speculatable willreturn memory(none)
declare { i32, i1 } @llvm.smul.with.overflow.i32(i32, i32) #1

; Function Attrs: mustprogress nocallback nofree nosync nounwind speculatable willreturn memory(none)
declare { i32, i1 } @llvm.uadd.with.overflow.i32(i32, i32) #1

attributes #0 = { mustprogress nofree norecurse nosync nounwind willreturn memory(none) "frame-pointer"="non-leaf" "probe-stack"="inline-asm" "target-cpu"="apple-m1" }
attributes #1 = { mustprogress nocallback nofree nosync nounwind speculatable willreturn memory(none) }

!llvm.module.flags = !{!0}
!llvm.ident = !{!1}

!0 = !{i32 8, !"PIC Level", i32 2}
!1 = !{!"rustc version 1.90.0 (1159e78c4 2025-09-14)"}
!2 = !{}
