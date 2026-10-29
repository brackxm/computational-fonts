; ModuleID = 'dispatch.9ffb28b3bae6f985-cgu.0'
source_filename = "dispatch.9ffb28b3bae6f985-cgu.0"
target datalayout = "e-m:o-p270:32:32-p271:32:32-p272:64:64-i64:64-i128:128-n32:64-S128-Fn32"
target triple = "arm64-apple-macosx11.0.0"

@_ZN8dispatch10INITIALIZE17h8484f48d0712669cE = constant ptr @_ZN8dispatch10initialize17h3882c5e40badf199E, section "__DATA,__mod_init_func", align 8
@_ZN8dispatch4BASE17hf8d24e6dd87ec43bE = local_unnamed_addr global [4 x i8] zeroinitializer, align 4
@_ZN8dispatch6CHOSEN17he579ae75e4f18ad0E = local_unnamed_addr global [8 x i8] zeroinitializer, align 8
@_ZN8dispatch10OPERATIONS17h4af2e596a18f003dE = internal unnamed_addr constant <{ ptr, ptr, ptr, ptr }> <{ ptr @_ZN8dispatch3add17h3920c75b93d9c2b4E, ptr @_ZN8dispatch3sub17h9b0175d27ccbe2e7E, ptr @_ZN8dispatch3mix17h7c9444f6ee351d34E, ptr @_ZN8dispatch4bump17hb8a408587fc36a01E }>, align 8
@llvm.used = appending global [1 x ptr] [ptr @_ZN8dispatch10INITIALIZE17h8484f48d0712669cE], section "llvm.metadata"

; dispatch::add
; Function Attrs: mustprogress nofree noinline norecurse nosync nounwind willreturn memory(read, argmem: none, inaccessiblemem: none)
define internal noundef i32 @_ZN8dispatch3add17h3920c75b93d9c2b4E(i32 noundef %a, i32 noundef %b) unnamed_addr #0 {
start:
  %_0.i1 = add i32 %b, %a
  %_4 = load i32, ptr @_ZN8dispatch4BASE17hf8d24e6dd87ec43bE, align 4, !noundef !2
  %_0.i = add i32 %_0.i1, %_4
  ret i32 %_0.i
}

; dispatch::sub
; Function Attrs: mustprogress nofree noinline norecurse nosync nounwind willreturn memory(read, argmem: none, inaccessiblemem: none)
define internal noundef i32 @_ZN8dispatch3sub17h9b0175d27ccbe2e7E(i32 noundef %a, i32 noundef %b) unnamed_addr #0 {
start:
  %_0.i1 = sub i32 %a, %b
  %_4 = load i32, ptr @_ZN8dispatch4BASE17hf8d24e6dd87ec43bE, align 4, !noundef !2
  %_0.i = add i32 %_0.i1, %_4
  ret i32 %_0.i
}

; dispatch::mix
; Function Attrs: mustprogress nofree noinline norecurse nosync nounwind willreturn memory(read, argmem: none, inaccessiblemem: none)
define noundef i32 @_ZN8dispatch3mix17h7c9444f6ee351d34E(i32 noundef %a, i32 noundef %b) unnamed_addr #0 {
start:
  %_3 = xor i32 %b, %a
  %_4 = load i32, ptr @_ZN8dispatch4BASE17hf8d24e6dd87ec43bE, align 4, !noundef !2
  %_0 = xor i32 %_3, %_4
  ret i32 %_0
}

; dispatch::bump
; Function Attrs: mustprogress nofree noinline norecurse nosync nounwind willreturn memory(readwrite, argmem: none, inaccessiblemem: none)
define internal noundef i32 @_ZN8dispatch4bump17hb8a408587fc36a01E(i32 noundef %a, i32 noundef %b) unnamed_addr #1 {
start:
  %_4 = load i32, ptr @_ZN8dispatch4BASE17hf8d24e6dd87ec43bE, align 4, !noundef !2
  %_0.i1 = add i32 %_4, %a
  store i32 %_0.i1, ptr @_ZN8dispatch4BASE17hf8d24e6dd87ec43bE, align 4
  %_0.i = add i32 %_0.i1, %b
  ret i32 %_0.i
}

; dispatch::initialize
; Function Attrs: mustprogress nofree norecurse nosync nounwind willreturn memory(write, argmem: none, inaccessiblemem: none)
define internal void @_ZN8dispatch10initialize17h3882c5e40badf199E() unnamed_addr #2 {
start:
  store i32 22, ptr @_ZN8dispatch4BASE17hf8d24e6dd87ec43bE, align 4
  store ptr @_ZN8dispatch3mix17h7c9444f6ee351d34E, ptr @_ZN8dispatch6CHOSEN17he579ae75e4f18ad0E, align 8
  ret void
}

; Function Attrs: mustprogress nofree norecurse nosync nounwind willreturn memory(write, argmem: none, inaccessiblemem: none)
define void @rust_reset_reference() unnamed_addr #2 {
start:
  store i32 22, ptr @_ZN8dispatch4BASE17hf8d24e6dd87ec43bE, align 4
  store ptr @_ZN8dispatch3mix17h7c9444f6ee351d34E, ptr @_ZN8dispatch6CHOSEN17he579ae75e4f18ad0E, align 8
  ret void
}

; dispatch::apply
; Function Attrs: noinline nounwind
define internal fastcc noundef i32 @_ZN8dispatch5apply17h42c90aef4920f2a7E(ptr nocapture noundef nonnull readonly %operation, i32 noundef %a, i32 noundef %b) unnamed_addr #3 {
start:
  %_0 = tail call noundef i32 %operation(i32 noundef %a, i32 noundef %b) #8
  ret i32 %_0
}

; Function Attrs: nounwind
define noundef i32 @rust_dispatch(i32 noundef %index, i32 noundef %a, i32 noundef %b) unnamed_addr #4 {
start:
  %_7 = and i32 %index, 3
  %_6 = zext nneg i32 %_7 to i64
  %0 = getelementptr inbounds nuw ptr, ptr @_ZN8dispatch10OPERATIONS17h4af2e596a18f003dE, i64 %_6
  %_4 = load ptr, ptr %0, align 8, !nonnull !2, !noundef !2
; call dispatch::apply
  %_0 = tail call fastcc noundef i32 @_ZN8dispatch5apply17h42c90aef4920f2a7E(ptr noundef nonnull %_4, i32 noundef %a, i32 noundef %b) #8
  ret i32 %_0
}

; Function Attrs: nounwind
define noundef i32 @rust_constructor_dispatch(i32 noundef %a, i32 noundef %b) unnamed_addr #4 {
start:
  %0 = load ptr, ptr @_ZN8dispatch6CHOSEN17he579ae75e4f18ad0E, align 8, !noundef !2
  %.not = icmp eq ptr %0, null
  br i1 %.not, label %bb4, label %bb3

bb3:                                              ; preds = %start
; call dispatch::apply
  %1 = tail call fastcc noundef i32 @_ZN8dispatch5apply17h42c90aef4920f2a7E(ptr noundef nonnull %0, i32 noundef %a, i32 noundef %b) #8
  br label %bb4

bb4:                                              ; preds = %start, %bb3
  %_0.sroa.0.0 = phi i32 [ %1, %bb3 ], [ 0, %start ]
  ret i32 %_0.sroa.0.0
}

; Function Attrs: nounwind
define noundef i32 @rust_dispatch_twice(i32 noundef %index, i32 noundef %a, i32 noundef %b) unnamed_addr #4 {
start:
  %_7 = and i32 %index, 3
  %_6 = zext nneg i32 %_7 to i64
  %0 = getelementptr inbounds nuw ptr, ptr @_ZN8dispatch10OPERATIONS17h4af2e596a18f003dE, i64 %_6
  %operation = load ptr, ptr %0, align 8, !nonnull !2, !noundef !2
; call dispatch::apply
  %_9 = tail call fastcc noundef i32 @_ZN8dispatch5apply17h42c90aef4920f2a7E(ptr noundef nonnull %operation, i32 noundef %a, i32 noundef %b) #8
; call dispatch::apply
  %_10 = tail call fastcc noundef i32 @_ZN8dispatch5apply17h42c90aef4920f2a7E(ptr noundef nonnull %operation, i32 noundef %b, i32 noundef %a) #8
  %_0 = xor i32 %_10, %_9
  ret i32 %_0
}

; dispatch::copy_two
; Function Attrs: mustprogress nofree noinline norecurse nosync nounwind willreturn memory(argmem: readwrite)
define internal fastcc void @_ZN8dispatch8copy_two17h0886db89fbb50d4bE(ptr nocapture noundef nonnull writeonly initializes((0, 16)) %dest) unnamed_addr #5 {
start:
  tail call void @llvm.memcpy.p0.p0.i64(ptr noundef nonnull align 8 dereferenceable(16) %dest, ptr noundef nonnull align 8 dereferenceable(16) @_ZN8dispatch10OPERATIONS17h4af2e596a18f003dE, i64 16, i1 false)
  ret void
}

; Function Attrs: nounwind
define noundef i32 @rust_copied_dispatch(i32 noundef %index, i32 noundef %a, i32 noundef %b) unnamed_addr #4 {
start:
  %local = alloca [16 x i8], align 8
  call void @llvm.lifetime.start.p0(i64 16, ptr nonnull %local)
; call dispatch::copy_two
  call fastcc void @_ZN8dispatch8copy_two17h0886db89fbb50d4bE(ptr noundef %local) #8
  %_14 = and i32 %index, 1
  %_13 = zext nneg i32 %_14 to i64
  %_0.i = getelementptr inbounds nuw ptr, ptr %local, i64 %_13
  %_11 = load ptr, ptr %_0.i, align 8, !nonnull !2, !noundef !2
; call dispatch::apply
  %_0 = tail call fastcc noundef i32 @_ZN8dispatch5apply17h42c90aef4920f2a7E(ptr noundef nonnull %_11, i32 noundef %a, i32 noundef %b) #8
  call void @llvm.lifetime.end.p0(i64 16, ptr nonnull %local)
  ret i32 %_0
}

; Function Attrs: mustprogress nocallback nofree nounwind willreturn memory(argmem: readwrite)
declare void @llvm.memcpy.p0.p0.i64(ptr noalias nocapture writeonly, ptr noalias nocapture readonly, i64, i1 immarg) #6

; Function Attrs: mustprogress nocallback nofree nosync nounwind willreturn memory(argmem: readwrite)
declare void @llvm.lifetime.start.p0(i64 immarg, ptr nocapture) #7

; Function Attrs: mustprogress nocallback nofree nosync nounwind willreturn memory(argmem: readwrite)
declare void @llvm.lifetime.end.p0(i64 immarg, ptr nocapture) #7

attributes #0 = { mustprogress nofree noinline norecurse nosync nounwind willreturn memory(read, argmem: none, inaccessiblemem: none) "frame-pointer"="non-leaf" "probe-stack"="inline-asm" "target-cpu"="apple-m1" }
attributes #1 = { mustprogress nofree noinline norecurse nosync nounwind willreturn memory(readwrite, argmem: none, inaccessiblemem: none) "frame-pointer"="non-leaf" "probe-stack"="inline-asm" "target-cpu"="apple-m1" }
attributes #2 = { mustprogress nofree norecurse nosync nounwind willreturn memory(write, argmem: none, inaccessiblemem: none) "frame-pointer"="non-leaf" "probe-stack"="inline-asm" "target-cpu"="apple-m1" }
attributes #3 = { noinline nounwind "frame-pointer"="non-leaf" "probe-stack"="inline-asm" "target-cpu"="apple-m1" }
attributes #4 = { nounwind "frame-pointer"="non-leaf" "probe-stack"="inline-asm" "target-cpu"="apple-m1" }
attributes #5 = { mustprogress nofree noinline norecurse nosync nounwind willreturn memory(argmem: readwrite) "frame-pointer"="non-leaf" "probe-stack"="inline-asm" "target-cpu"="apple-m1" }
attributes #6 = { mustprogress nocallback nofree nounwind willreturn memory(argmem: readwrite) }
attributes #7 = { mustprogress nocallback nofree nosync nounwind willreturn memory(argmem: readwrite) }
attributes #8 = { nounwind }

!llvm.module.flags = !{!0}
!llvm.ident = !{!1}

!0 = !{i32 8, !"PIC Level", i32 2}
!1 = !{!"rustc version 1.90.0 (1159e78c4 2025-09-14)"}
!2 = !{}
