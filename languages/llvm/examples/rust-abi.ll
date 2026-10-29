; ModuleID = 'abi.36f31bee4d823f3-cgu.0'
source_filename = "abi.36f31bee4d823f3-cgu.0"
target datalayout = "e-m:o-p270:32:32-p271:32:32-p272:64:64-i64:64-i128:128-n32:64-S128-Fn32"
target triple = "arm64-apple-macosx11.0.0"

@_ZN3abi6MAKERS17ha9efc80a8e1ce14aE = internal unnamed_addr constant <{ ptr, ptr }> <{ ptr @rust_triple, ptr @rust_reverse_triple }>, align 8

; Function Attrs: mustprogress nofree noinline norecurse nosync nounwind willreturn memory(argmem: write)
define void @rust_triple(ptr dead_on_unwind noalias nocapture noundef writable writeonly sret([24 x i8]) align 8 dereferenceable(24) initializes((0, 24)) %_0, i64 noundef %x, i64 noundef %y) unnamed_addr #0 {
start:
  %_0.i = add i64 %y, %x
  %_4 = xor i64 %y, %x
  %_0.i1 = sub i64 %x, %y
  store i64 %_0.i, ptr %_0, align 8
  %0 = getelementptr inbounds nuw i8, ptr %_0, i64 8
  store i64 %_4, ptr %0, align 8
  %1 = getelementptr inbounds nuw i8, ptr %_0, i64 16
  store i64 %_0.i1, ptr %1, align 8
  ret void
}

; Function Attrs: mustprogress nofree noinline norecurse nosync nounwind willreturn memory(argmem: write)
define void @rust_reverse_triple(ptr dead_on_unwind noalias nocapture noundef writable writeonly sret([24 x i8]) align 8 dereferenceable(24) initializes((0, 24)) %_0, i64 noundef %x, i64 noundef %y) unnamed_addr #0 {
start:
  tail call void @rust_triple(ptr noalias nocapture noundef nonnull sret([24 x i8]) align 8 dereferenceable(24) %_0, i64 noundef %y, i64 noundef %x) #5
  ret void
}

; Function Attrs: mustprogress nofree noinline norecurse nosync nounwind willreturn memory(argmem: readwrite)
define noundef i64 @rust_use_triple(ptr noalias nocapture noundef align 8 dereferenceable(24) %value) unnamed_addr #1 {
start:
  %_3 = load i64, ptr %value, align 8, !noundef !2
  %_0.i = add i64 %_3, 7
  store i64 %_0.i, ptr %value, align 8
  %0 = getelementptr inbounds nuw i8, ptr %value, i64 8
  %_6 = load i64, ptr %0, align 8, !noundef !2
  %1 = getelementptr inbounds nuw i8, ptr %value, i64 16
  %_7 = load i64, ptr %1, align 8, !noundef !2
  %2 = xor i64 %_6, %_7
  %_0 = xor i64 %2, %_0.i
  ret i64 %_0
}

; Function Attrs: mustprogress nofree norecurse nosync nounwind willreturn memory(none)
define noundef i64 @rust_call_triple(i64 noundef %x, i64 noundef %y) unnamed_addr #2 {
start:
  %_3 = alloca [24 x i8], align 8
  call void @llvm.lifetime.start.p0(i64 24, ptr nonnull %_3)
  call void @rust_triple(ptr noalias nocapture noundef nonnull sret([24 x i8]) align 8 dereferenceable(24) %_3, i64 noundef %x, i64 noundef %y) #5
  %_0 = call noundef i64 @rust_use_triple(ptr noalias nocapture noundef nonnull align 8 dereferenceable(24) %_3) #5
  call void @llvm.lifetime.end.p0(i64 24, ptr nonnull %_3)
  ret i64 %_0
}

; Function Attrs: nounwind
define void @rust_choose_triple(ptr dead_on_unwind noalias nocapture noundef writable sret([24 x i8]) align 8 dereferenceable(24) %_0, i32 noundef %which, i64 noundef %x, i64 noundef %y) unnamed_addr #3 {
start:
  %_7 = and i32 %which, 1
  %_6 = zext nneg i32 %_7 to i64
  %0 = getelementptr inbounds nuw ptr, ptr @_ZN3abi6MAKERS17ha9efc80a8e1ce14aE, i64 %_6
  %_4 = load ptr, ptr %0, align 8, !nonnull !2, !noundef !2
  tail call void %_4(ptr noalias nocapture noundef nonnull sret([24 x i8]) align 8 dereferenceable(24) %_0, i64 noundef %x, i64 noundef %y) #5
  ret void
}

; Function Attrs: mustprogress nocallback nofree nosync nounwind willreturn memory(argmem: readwrite)
declare void @llvm.lifetime.start.p0(i64 immarg, ptr nocapture) #4

; Function Attrs: mustprogress nocallback nofree nosync nounwind willreturn memory(argmem: readwrite)
declare void @llvm.lifetime.end.p0(i64 immarg, ptr nocapture) #4

attributes #0 = { mustprogress nofree noinline norecurse nosync nounwind willreturn memory(argmem: write) "frame-pointer"="non-leaf" "probe-stack"="inline-asm" "target-cpu"="apple-m1" }
attributes #1 = { mustprogress nofree noinline norecurse nosync nounwind willreturn memory(argmem: readwrite) "frame-pointer"="non-leaf" "probe-stack"="inline-asm" "target-cpu"="apple-m1" }
attributes #2 = { mustprogress nofree norecurse nosync nounwind willreturn memory(none) "frame-pointer"="non-leaf" "probe-stack"="inline-asm" "target-cpu"="apple-m1" }
attributes #3 = { nounwind "frame-pointer"="non-leaf" "probe-stack"="inline-asm" "target-cpu"="apple-m1" }
attributes #4 = { mustprogress nocallback nofree nosync nounwind willreturn memory(argmem: readwrite) }
attributes #5 = { nounwind }

!llvm.module.flags = !{!0}
!llvm.ident = !{!1}

!0 = !{i32 8, !"PIC Level", i32 2}
!1 = !{!"rustc version 1.90.0 (1159e78c4 2025-09-14)"}
!2 = !{}
