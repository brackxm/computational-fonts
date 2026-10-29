; ModuleID = 'aliases.a1778277701d67ce-cgu.0'
source_filename = "aliases.a1778277701d67ce-cgu.0"
target datalayout = "e-m:o-p270:32:32-p271:32:32-p272:64:64-i64:64-i128:128-n32:64-S128-Fn32"
target triple = "arm64-apple-macosx11.0.0"

; Function Attrs: mustprogress nofree noinline norecurse nosync nounwind willreturn memory(none)
define noundef i32 @original(i32 noundef %x) unnamed_addr #0 {
start:
  %_0.i = add i32 %x, 7
  ret i32 %_0.i
}

; Function Attrs: mustprogress nofree noinline norecurse nosync nounwind willreturn memory(none)
define noundef i32 @duplicate(i32 noundef %x) unnamed_addr #0 {
start:
  %_0.i = add i32 %x, 7
  ret i32 %_0.i
}

; Function Attrs: nounwind
define noundef i32 @alias_dispatch(i32 noundef %which, i32 noundef %x) unnamed_addr #1 {
start:
  %_4 = and i32 %which, 1
  %0 = icmp eq i32 %_4, 0
  %original.duplicate = select i1 %0, ptr @original, ptr @duplicate
  %_0 = tail call noundef i32 %original.duplicate(i32 noundef %x) #2, !callees !2
  ret i32 %_0
}

attributes #0 = { mustprogress nofree noinline norecurse nosync nounwind willreturn memory(none) "frame-pointer"="non-leaf" "probe-stack"="inline-asm" "target-cpu"="apple-m1" }
attributes #1 = { nounwind "frame-pointer"="non-leaf" "probe-stack"="inline-asm" "target-cpu"="apple-m1" }
attributes #2 = { nounwind }

!llvm.module.flags = !{!0}
!llvm.ident = !{!1}

!0 = !{i32 8, !"PIC Level", i32 2}
!1 = !{!"rustc version 1.90.0 (1159e78c4 2025-09-14)"}
!2 = !{ptr @duplicate, ptr @original}
