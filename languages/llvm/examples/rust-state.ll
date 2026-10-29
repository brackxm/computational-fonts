; ModuleID = 'state.ec68de4fbe0a41de-cgu.0'
source_filename = "state.ec68de4fbe0a41de-cgu.0"
target datalayout = "e-m:o-p270:32:32-p271:32:32-p272:64:64-i64:64-i128:128-n32:64-S128-Fn32"
target triple = "arm64-apple-macosx11.0.0"

@_ZN5state7COUNTER17h13f31c249e46562aE.0 = internal unnamed_addr global i32 5, align 4
@_ZN5state5FIRST17h502f5b339c54a8a8E = internal global [4 x i8] c"\03\00\00\00", align 4
@_ZN5state6SECOND17he387977256a98f07E = internal global [4 x i8] c"\0B\00\00\00", align 4
@_ZN5state5SLOTS17hcbc627832b520bc7E = internal unnamed_addr global <{ ptr, ptr }> <{ ptr @_ZN5state5FIRST17h502f5b339c54a8a8E, ptr @_ZN5state6SECOND17he387977256a98f07E }>, align 8

; Function Attrs: mustprogress nofree norecurse nosync nounwind willreturn memory(none)
define noundef i32 @rust_saturating_add(i32 noundef %a, i32 noundef %b) unnamed_addr #0 {
start:
  %0 = tail call noundef i32 @llvm.uadd.sat.i32(i32 %a, i32 %b)
  ret i32 %0
}

; Function Attrs: mustprogress nofree norecurse nosync nounwind willreturn memory(none)
define noundef i32 @rust_saturating_sub(i32 noundef %a, i32 noundef %b) unnamed_addr #0 {
start:
  %0 = tail call noundef i32 @llvm.ssub.sat.i32(i32 %a, i32 %b)
  ret i32 %0
}

; state::advance
; Function Attrs: mustprogress nofree noinline norecurse nosync nounwind willreturn memory(readwrite, argmem: none, inaccessiblemem: none)
define internal fastcc noundef i32 @_ZN5state7advance17h3dad5b6e191589c4E(i32 noundef %value) unnamed_addr #1 {
start:
  %_3 = load i32, ptr @_ZN5state7COUNTER17h13f31c249e46562aE.0, align 4, !noundef !2
  %_0.i = add i32 %_3, %value
  store i32 %_0.i, ptr @_ZN5state7COUNTER17h13f31c249e46562aE.0, align 4
  ret i32 %_0.i
}

; Function Attrs: mustprogress nofree norecurse nosync nounwind willreturn memory(readwrite, inaccessiblemem: none)
define noundef i32 @rust_global_calls(i32 noundef %a, i32 noundef %b) unnamed_addr #2 {
start:
  store i32 5, ptr @_ZN5state7COUNTER17h13f31c249e46562aE.0, align 4
; call state::advance
  %_4 = tail call fastcc noundef i32 @_ZN5state7advance17h3dad5b6e191589c4E(i32 noundef %a) #10
; call state::advance
  %_5 = tail call fastcc noundef i32 @_ZN5state7advance17h3dad5b6e191589c4E(i32 noundef %b) #10
  %_0 = xor i32 %_5, %_4
  ret i32 %_0
}

; Function Attrs: mustprogress nofree norecurse nosync nounwind willreturn memory(readwrite, argmem: write, inaccessiblemem: none)
define noundef i32 @rust_pointer_table(i32 noundef %index, i32 noundef %value) unnamed_addr #3 {
start:
  store i32 3, ptr @_ZN5state5FIRST17h502f5b339c54a8a8E, align 4
  store i32 11, ptr @_ZN5state6SECOND17he387977256a98f07E, align 4
  %_7 = and i32 %index, 1
  %_6 = zext nneg i32 %_7 to i64
  %0 = getelementptr inbounds nuw ptr, ptr @_ZN5state5SLOTS17hcbc627832b520bc7E, i64 %_6
  store ptr @_ZN5state5FIRST17h502f5b339c54a8a8E, ptr %0, align 8
  %1 = and i32 %index, 1
  %_10 = xor i32 %1, 1
  %_9 = zext nneg i32 %_10 to i64
  %2 = getelementptr inbounds nuw ptr, ptr @_ZN5state5SLOTS17hcbc627832b520bc7E, i64 %_9
  store ptr @_ZN5state6SECOND17he387977256a98f07E, ptr %2, align 8
  %_19 = load ptr, ptr %0, align 8, !noundef !2
  store i32 %value, ptr %_19, align 4
  %_13 = load i32, ptr @_ZN5state6SECOND17he387977256a98f07E, align 4, !noundef !2
  %_0.i = add i32 %_13, %value
  ret i32 %_0.i
}

; state::copy_pointers
; Function Attrs: mustprogress nofree noinline norecurse nosync nounwind willreturn memory(argmem: readwrite)
define internal fastcc void @_ZN5state13copy_pointers17h3ac214b0293f94fdE(ptr nocapture noundef nonnull writeonly initializes((0, 16)) %dest, ptr nocapture noundef nonnull readonly %source) unnamed_addr #4 {
start:
  tail call void @llvm.memcpy.p0.p0.i64(ptr noundef nonnull align 8 dereferenceable(16) %dest, ptr noundef nonnull align 8 dereferenceable(16) %source, i64 16, i1 false)
  ret void
}

; Function Attrs: mustprogress nofree norecurse nosync nounwind willreturn memory(read, inaccessiblemem: none)
define noundef i32 @rust_pointer_copy(i32 noundef %index, i32 noundef %value) unnamed_addr #5 {
start:
  %dest = alloca [16 x i8], align 8
  %source = alloca [16 x i8], align 8
  %values = alloca [8 x i8], align 4
  call void @llvm.lifetime.start.p0(i64 8, ptr nonnull %values)
  %_0.i = add i32 %value, 1
  store i32 %value, ptr %values, align 4
  %0 = getelementptr inbounds nuw i8, ptr %values, i64 4
  store i32 %_0.i, ptr %0, align 4
  call void @llvm.lifetime.start.p0(i64 16, ptr nonnull %source)
  store ptr %values, ptr %source, align 8
  %1 = getelementptr inbounds nuw i8, ptr %source, i64 8
  store ptr %0, ptr %1, align 8
  call void @llvm.lifetime.start.p0(i64 16, ptr nonnull %dest)
  call void @llvm.memset.p0.i64(ptr noundef nonnull align 8 dereferenceable(16) %dest, i8 0, i64 16, i1 false)
; call state::copy_pointers
  call fastcc void @_ZN5state13copy_pointers17h3ac214b0293f94fdE(ptr noundef %dest, ptr noundef %source) #10
  %_23 = and i32 %index, 1
  %_22 = zext nneg i32 %_23 to i64
  %2 = getelementptr inbounds nuw ptr, ptr %dest, i64 %_22
  %_25 = load ptr, ptr %2, align 8, !noundef !2
  %_0 = load i32, ptr %_25, align 4, !noundef !2
  call void @llvm.lifetime.end.p0(i64 16, ptr nonnull %dest)
  call void @llvm.lifetime.end.p0(i64 16, ptr nonnull %source)
  call void @llvm.lifetime.end.p0(i64 8, ptr nonnull %values)
  ret i32 %_0
}

; Function Attrs: mustprogress nocallback nofree nosync nounwind willreturn memory(argmem: readwrite)
declare void @llvm.lifetime.start.p0(i64 immarg, ptr nocapture) #6

; Function Attrs: mustprogress nocallback nofree nosync nounwind speculatable willreturn memory(none)
declare i32 @llvm.ssub.sat.i32(i32, i32) #7

; Function Attrs: mustprogress nocallback nofree nosync nounwind willreturn memory(argmem: readwrite)
declare void @llvm.lifetime.end.p0(i64 immarg, ptr nocapture) #6

; Function Attrs: mustprogress nocallback nofree nosync nounwind speculatable willreturn memory(none)
declare i32 @llvm.uadd.sat.i32(i32, i32) #7

; Function Attrs: mustprogress nocallback nofree nounwind willreturn memory(argmem: readwrite)
declare void @llvm.memcpy.p0.p0.i64(ptr noalias nocapture writeonly, ptr noalias nocapture readonly, i64, i1 immarg) #8

; Function Attrs: nocallback nofree nounwind willreturn memory(argmem: write)
declare void @llvm.memset.p0.i64(ptr nocapture writeonly, i8, i64, i1 immarg) #9

attributes #0 = { mustprogress nofree norecurse nosync nounwind willreturn memory(none) "frame-pointer"="non-leaf" "probe-stack"="inline-asm" "target-cpu"="apple-m1" }
attributes #1 = { mustprogress nofree noinline norecurse nosync nounwind willreturn memory(readwrite, argmem: none, inaccessiblemem: none) "frame-pointer"="non-leaf" "probe-stack"="inline-asm" "target-cpu"="apple-m1" }
attributes #2 = { mustprogress nofree norecurse nosync nounwind willreturn memory(readwrite, inaccessiblemem: none) "frame-pointer"="non-leaf" "probe-stack"="inline-asm" "target-cpu"="apple-m1" }
attributes #3 = { mustprogress nofree norecurse nosync nounwind willreturn memory(readwrite, argmem: write, inaccessiblemem: none) "frame-pointer"="non-leaf" "probe-stack"="inline-asm" "target-cpu"="apple-m1" }
attributes #4 = { mustprogress nofree noinline norecurse nosync nounwind willreturn memory(argmem: readwrite) "frame-pointer"="non-leaf" "probe-stack"="inline-asm" "target-cpu"="apple-m1" }
attributes #5 = { mustprogress nofree norecurse nosync nounwind willreturn memory(read, inaccessiblemem: none) "frame-pointer"="non-leaf" "probe-stack"="inline-asm" "target-cpu"="apple-m1" }
attributes #6 = { mustprogress nocallback nofree nosync nounwind willreturn memory(argmem: readwrite) }
attributes #7 = { mustprogress nocallback nofree nosync nounwind speculatable willreturn memory(none) }
attributes #8 = { mustprogress nocallback nofree nounwind willreturn memory(argmem: readwrite) }
attributes #9 = { nocallback nofree nounwind willreturn memory(argmem: write) }
attributes #10 = { nounwind }

!llvm.module.flags = !{!0}
!llvm.ident = !{!1}

!0 = !{i32 8, !"PIC Level", i32 2}
!1 = !{!"rustc version 1.90.0 (1159e78c4 2025-09-14)"}
!2 = !{}
