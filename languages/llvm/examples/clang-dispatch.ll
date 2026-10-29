; ModuleID = 'languages/llvm/examples/dispatch.c'
source_filename = "languages/llvm/examples/dispatch.c"
target datalayout = "e-m:o-i64:64-i128:128-n32:64-S128-Fn32"
target triple = "arm64-apple-macosx15.0.0"

@base = internal unnamed_addr global i32 22, align 4
@operations = internal unnamed_addr constant [4 x ptr] [ptr @add, ptr @sub, ptr @mix, ptr @bump], align 8
@llvm.global_ctors = appending global [0 x { i32, ptr, ptr }] zeroinitializer

; Function Attrs: mustprogress nofree noinline norecurse nosync nounwind ssp willreturn memory(read, argmem: none, inaccessiblemem: none) uwtable(sync)
define internal i32 @mix(i32 noundef %0, i32 noundef %1) #0 {
  %3 = xor i32 %1, %0
  %4 = load i32, ptr @base, align 4, !tbaa !6
  %5 = xor i32 %3, %4
  ret i32 %5
}

; Function Attrs: mustprogress nofree norecurse nosync nounwind ssp willreturn memory(write, argmem: none, inaccessiblemem: none) uwtable(sync)
define void @reset_reference() local_unnamed_addr #1 {
  store i32 22, ptr @base, align 4, !tbaa !6
  ret void
}

; Function Attrs: nounwind ssp uwtable(sync)
define i32 @dispatch(i32 noundef %0, i32 noundef %1, i32 noundef %2) local_unnamed_addr #2 {
  %4 = and i32 %0, 3
  %5 = zext nneg i32 %4 to i64
  %6 = getelementptr inbounds [4 x ptr], ptr @operations, i64 0, i64 %5
  %7 = load ptr, ptr %6, align 8, !tbaa !10
  %8 = tail call fastcc i32 @apply(ptr noundef %7, i32 noundef %1, i32 noundef %2)
  ret i32 %8
}

; Function Attrs: noinline nounwind ssp uwtable(sync)
define internal fastcc i32 @apply(ptr nocapture noundef readonly %0, i32 noundef %1, i32 noundef %2) unnamed_addr #3 {
  %4 = tail call i32 %0(i32 noundef %1, i32 noundef %2) #8
  ret i32 %4
}

; Function Attrs: nounwind ssp uwtable(sync)
define i32 @constructor_dispatch(i32 noundef %0, i32 noundef %1) local_unnamed_addr #2 {
  %3 = tail call fastcc i32 @apply(ptr noundef nonnull @mix, i32 noundef %0, i32 noundef %1)
  ret i32 %3
}

; Function Attrs: nounwind ssp uwtable(sync)
define i32 @dispatch_twice(i32 noundef %0, i32 noundef %1, i32 noundef %2) local_unnamed_addr #2 {
  %4 = and i32 %0, 3
  %5 = zext nneg i32 %4 to i64
  %6 = getelementptr inbounds [4 x ptr], ptr @operations, i64 0, i64 %5
  %7 = load ptr, ptr %6, align 8, !tbaa !10
  %8 = tail call fastcc i32 @apply(ptr noundef %7, i32 noundef %1, i32 noundef %2)
  %9 = tail call fastcc i32 @apply(ptr noundef %7, i32 noundef %2, i32 noundef %1)
  %10 = xor i32 %9, %8
  ret i32 %10
}

; Function Attrs: mustprogress nocallback nofree nosync nounwind willreturn memory(argmem: readwrite)
declare void @llvm.lifetime.start.p0(i64 immarg, ptr nocapture) #4

; Function Attrs: mustprogress nocallback nofree nosync nounwind willreturn memory(argmem: readwrite)
declare void @llvm.lifetime.end.p0(i64 immarg, ptr nocapture) #4

; Function Attrs: nounwind ssp uwtable(sync)
define i32 @copied_dispatch(i32 noundef %0, i32 noundef %1, i32 noundef %2) local_unnamed_addr #2 {
  %4 = alloca [2 x ptr], align 8
  call void @llvm.lifetime.start.p0(i64 16, ptr nonnull %4) #8
  call fastcc void @copy_two(ptr noundef nonnull %4)
  %5 = and i32 %0, 1
  %6 = zext nneg i32 %5 to i64
  %7 = getelementptr inbounds [2 x ptr], ptr %4, i64 0, i64 %6
  %8 = load ptr, ptr %7, align 8, !tbaa !10
  %9 = tail call fastcc i32 @apply(ptr noundef %8, i32 noundef %1, i32 noundef %2)
  call void @llvm.lifetime.end.p0(i64 16, ptr nonnull %4) #8
  ret i32 %9
}

; Function Attrs: mustprogress nofree noinline norecurse nosync nounwind ssp willreturn memory(argmem: readwrite) uwtable(sync)
define internal fastcc void @copy_two(ptr nocapture noundef writeonly %0) unnamed_addr #5 {
  tail call void @llvm.memcpy.p0.p0.i64(ptr noundef nonnull align 8 dereferenceable(16) %0, ptr noundef nonnull align 8 dereferenceable(16) @operations, i64 16, i1 false)
  ret void
}

; Function Attrs: mustprogress nofree noinline norecurse nosync nounwind ssp willreturn memory(read, argmem: none, inaccessiblemem: none) uwtable(sync)
define internal i32 @add(i32 noundef %0, i32 noundef %1) #0 {
  %3 = add i32 %1, %0
  %4 = load i32, ptr @base, align 4, !tbaa !6
  %5 = add i32 %3, %4
  ret i32 %5
}

; Function Attrs: mustprogress nofree noinline norecurse nosync nounwind ssp willreturn memory(read, argmem: none, inaccessiblemem: none) uwtable(sync)
define internal i32 @sub(i32 noundef %0, i32 noundef %1) #0 {
  %3 = sub i32 %0, %1
  %4 = load i32, ptr @base, align 4, !tbaa !6
  %5 = add i32 %3, %4
  ret i32 %5
}

; Function Attrs: mustprogress nofree noinline norecurse nosync nounwind ssp willreturn memory(readwrite, argmem: none, inaccessiblemem: none) uwtable(sync)
define internal i32 @bump(i32 noundef %0, i32 noundef %1) #6 {
  %3 = load i32, ptr @base, align 4, !tbaa !6
  %4 = add i32 %3, %0
  store i32 %4, ptr @base, align 4, !tbaa !6
  %5 = add i32 %4, %1
  ret i32 %5
}

; Function Attrs: mustprogress nocallback nofree nounwind willreturn memory(argmem: readwrite)
declare void @llvm.memcpy.p0.p0.i64(ptr noalias nocapture writeonly, ptr noalias nocapture readonly, i64, i1 immarg) #7

attributes #0 = { mustprogress nofree noinline norecurse nosync nounwind ssp willreturn memory(read, argmem: none, inaccessiblemem: none) uwtable(sync) "frame-pointer"="non-leaf" "no-trapping-math"="true" "probe-stack"="__chkstk_darwin" "stack-protector-buffer-size"="8" "target-cpu"="apple-m1" "target-features"="+aes,+altnzcv,+bti,+ccdp,+ccidx,+complxnum,+crc,+dit,+dotprod,+flagm,+fp-armv8,+fp16fml,+fptoint,+fullfp16,+jsconv,+lse,+neon,+pauth,+perfmon,+predres,+ras,+rcpc,+rdm,+sb,+sha2,+sha3,+specrestrict,+ssbs,+v8.1a,+v8.2a,+v8.3a,+v8.4a,+v8.5a,+v8a,+zcm,+zcz" }
attributes #1 = { mustprogress nofree norecurse nosync nounwind ssp willreturn memory(write, argmem: none, inaccessiblemem: none) uwtable(sync) "frame-pointer"="non-leaf" "no-trapping-math"="true" "probe-stack"="__chkstk_darwin" "stack-protector-buffer-size"="8" "target-cpu"="apple-m1" "target-features"="+aes,+altnzcv,+bti,+ccdp,+ccidx,+complxnum,+crc,+dit,+dotprod,+flagm,+fp-armv8,+fp16fml,+fptoint,+fullfp16,+jsconv,+lse,+neon,+pauth,+perfmon,+predres,+ras,+rcpc,+rdm,+sb,+sha2,+sha3,+specrestrict,+ssbs,+v8.1a,+v8.2a,+v8.3a,+v8.4a,+v8.5a,+v8a,+zcm,+zcz" }
attributes #2 = { nounwind ssp uwtable(sync) "frame-pointer"="non-leaf" "no-trapping-math"="true" "probe-stack"="__chkstk_darwin" "stack-protector-buffer-size"="8" "target-cpu"="apple-m1" "target-features"="+aes,+altnzcv,+bti,+ccdp,+ccidx,+complxnum,+crc,+dit,+dotprod,+flagm,+fp-armv8,+fp16fml,+fptoint,+fullfp16,+jsconv,+lse,+neon,+pauth,+perfmon,+predres,+ras,+rcpc,+rdm,+sb,+sha2,+sha3,+specrestrict,+ssbs,+v8.1a,+v8.2a,+v8.3a,+v8.4a,+v8.5a,+v8a,+zcm,+zcz" }
attributes #3 = { noinline nounwind ssp uwtable(sync) "frame-pointer"="non-leaf" "no-trapping-math"="true" "probe-stack"="__chkstk_darwin" "stack-protector-buffer-size"="8" "target-cpu"="apple-m1" "target-features"="+aes,+altnzcv,+bti,+ccdp,+ccidx,+complxnum,+crc,+dit,+dotprod,+flagm,+fp-armv8,+fp16fml,+fptoint,+fullfp16,+jsconv,+lse,+neon,+pauth,+perfmon,+predres,+ras,+rcpc,+rdm,+sb,+sha2,+sha3,+specrestrict,+ssbs,+v8.1a,+v8.2a,+v8.3a,+v8.4a,+v8.5a,+v8a,+zcm,+zcz" }
attributes #4 = { mustprogress nocallback nofree nosync nounwind willreturn memory(argmem: readwrite) }
attributes #5 = { mustprogress nofree noinline norecurse nosync nounwind ssp willreturn memory(argmem: readwrite) uwtable(sync) "frame-pointer"="non-leaf" "no-trapping-math"="true" "probe-stack"="__chkstk_darwin" "stack-protector-buffer-size"="8" "target-cpu"="apple-m1" "target-features"="+aes,+altnzcv,+bti,+ccdp,+ccidx,+complxnum,+crc,+dit,+dotprod,+flagm,+fp-armv8,+fp16fml,+fptoint,+fullfp16,+jsconv,+lse,+neon,+pauth,+perfmon,+predres,+ras,+rcpc,+rdm,+sb,+sha2,+sha3,+specrestrict,+ssbs,+v8.1a,+v8.2a,+v8.3a,+v8.4a,+v8.5a,+v8a,+zcm,+zcz" }
attributes #6 = { mustprogress nofree noinline norecurse nosync nounwind ssp willreturn memory(readwrite, argmem: none, inaccessiblemem: none) uwtable(sync) "frame-pointer"="non-leaf" "no-trapping-math"="true" "probe-stack"="__chkstk_darwin" "stack-protector-buffer-size"="8" "target-cpu"="apple-m1" "target-features"="+aes,+altnzcv,+bti,+ccdp,+ccidx,+complxnum,+crc,+dit,+dotprod,+flagm,+fp-armv8,+fp16fml,+fptoint,+fullfp16,+jsconv,+lse,+neon,+pauth,+perfmon,+predres,+ras,+rcpc,+rdm,+sb,+sha2,+sha3,+specrestrict,+ssbs,+v8.1a,+v8.2a,+v8.3a,+v8.4a,+v8.5a,+v8a,+zcm,+zcz" }
attributes #7 = { mustprogress nocallback nofree nounwind willreturn memory(argmem: readwrite) }
attributes #8 = { nounwind }

!llvm.module.flags = !{!0, !1, !2, !3, !4}
!llvm.ident = !{!5}

!0 = !{i32 2, !"SDK Version", [2 x i32] [i32 26, i32 2]}
!1 = !{i32 1, !"wchar_size", i32 4}
!2 = !{i32 8, !"PIC Level", i32 2}
!3 = !{i32 7, !"uwtable", i32 1}
!4 = !{i32 7, !"frame-pointer", i32 1}
!5 = !{!"Apple clang version 17.0.0 (clang-1700.6.4.2)"}
!6 = !{!7, !7, i64 0}
!7 = !{!"int", !8, i64 0}
!8 = !{!"omnipotent char", !9, i64 0}
!9 = !{!"Simple C/C++ TBAA"}
!10 = !{!11, !11, i64 0}
!11 = !{!"any pointer", !8, i64 0}
