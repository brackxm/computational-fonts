; ModuleID = 'languages/llvm/examples/state.c'
source_filename = "languages/llvm/examples/state.c"
target datalayout = "e-m:o-i64:64-i128:128-n32:64-S128-Fn32"
target triple = "arm64-apple-macosx15.0.0"

@counter = internal unnamed_addr global i32 5, align 4
@first = internal global i32 3, align 4
@second = internal global i32 11, align 4
@slots = internal unnamed_addr global [2 x ptr] [ptr @first, ptr @second], align 8

; Function Attrs: mustprogress nofree norecurse nosync nounwind ssp willreturn memory(none) uwtable(sync)
define noundef i32 @saturating_add(i32 noundef %0, i32 noundef %1) local_unnamed_addr #0 {
  %3 = tail call i32 @llvm.uadd.sat.i32(i32 %0, i32 %1)
  ret i32 %3
}

; Function Attrs: mustprogress nocallback nofree nosync nounwind speculatable willreturn memory(none)
declare i32 @llvm.uadd.sat.i32(i32, i32) #1

; Function Attrs: mustprogress nofree norecurse nosync nounwind ssp willreturn memory(none) uwtable(sync)
define noundef i32 @saturating_sub(i32 noundef %0, i32 noundef %1) local_unnamed_addr #0 {
  %3 = tail call i32 @llvm.ssub.sat.i32(i32 %0, i32 %1)
  ret i32 %3
}

; Function Attrs: mustprogress nocallback nofree nosync nounwind speculatable willreturn memory(none)
declare i32 @llvm.ssub.sat.i32(i32, i32) #1

; Function Attrs: mustprogress nofree norecurse nosync nounwind ssp willreturn memory(readwrite, inaccessiblemem: none) uwtable(sync)
define i32 @global_calls(i32 noundef %0, i32 noundef %1) local_unnamed_addr #2 {
  store i32 5, ptr @counter, align 4, !tbaa !6
  %3 = tail call fastcc i32 @advance(i32 noundef %0)
  %4 = tail call fastcc i32 @advance(i32 noundef %1)
  %5 = xor i32 %4, %3
  ret i32 %5
}

; Function Attrs: mustprogress nofree noinline norecurse nosync nounwind ssp willreturn memory(readwrite, argmem: none, inaccessiblemem: none) uwtable(sync)
define internal fastcc i32 @advance(i32 noundef %0) unnamed_addr #3 {
  %2 = load i32, ptr @counter, align 4, !tbaa !6
  %3 = add i32 %2, %0
  store i32 %3, ptr @counter, align 4, !tbaa !6
  ret i32 %3
}

; Function Attrs: mustprogress nofree norecurse nosync nounwind ssp willreturn memory(write, argmem: none, inaccessiblemem: none) uwtable(sync)
define noundef i32 @pointer_table(i32 noundef %0, i32 noundef %1) local_unnamed_addr #4 {
  store i32 3, ptr @first, align 4, !tbaa !6
  store i32 11, ptr @second, align 4, !tbaa !6
  %3 = and i32 %0, 1
  %4 = zext nneg i32 %3 to i64
  %5 = getelementptr inbounds [2 x ptr], ptr @slots, i64 0, i64 %4
  store ptr @first, ptr %5, align 8, !tbaa !10
  %6 = xor i32 %3, 1
  %7 = zext nneg i32 %6 to i64
  %8 = getelementptr inbounds [2 x ptr], ptr @slots, i64 0, i64 %7
  store ptr @second, ptr %8, align 8, !tbaa !10
  store i32 %1, ptr @first, align 4, !tbaa !6
  %9 = add i32 %1, 11
  ret i32 %9
}

; Function Attrs: mustprogress nofree norecurse nosync nounwind ssp willreturn memory(read, inaccessiblemem: none) uwtable(sync)
define i32 @pointer_copy(i32 noundef %0, i32 noundef %1) local_unnamed_addr #5 {
  %3 = alloca [2 x i32], align 4
  %4 = alloca [2 x ptr], align 8
  %5 = alloca [2 x ptr], align 8
  call void @llvm.lifetime.start.p0(i64 8, ptr nonnull %3) #9
  store i32 %1, ptr %3, align 4, !tbaa !6
  %6 = getelementptr inbounds i8, ptr %3, i64 4
  %7 = add i32 %1, 1
  store i32 %7, ptr %6, align 4, !tbaa !6
  call void @llvm.lifetime.start.p0(i64 16, ptr nonnull %4) #9
  store ptr %3, ptr %4, align 8, !tbaa !10
  %8 = getelementptr inbounds i8, ptr %4, i64 8
  store ptr %6, ptr %8, align 8, !tbaa !10
  call void @llvm.lifetime.start.p0(i64 16, ptr nonnull %5) #9
  call fastcc void @copy_pointers(ptr noundef nonnull %5, ptr noundef nonnull %4)
  %9 = and i32 %0, 1
  %10 = zext nneg i32 %9 to i64
  %11 = getelementptr inbounds [2 x ptr], ptr %5, i64 0, i64 %10
  %12 = load ptr, ptr %11, align 8, !tbaa !10
  %13 = load i32, ptr %12, align 4, !tbaa !6
  call void @llvm.lifetime.end.p0(i64 16, ptr nonnull %5) #9
  call void @llvm.lifetime.end.p0(i64 16, ptr nonnull %4) #9
  call void @llvm.lifetime.end.p0(i64 8, ptr nonnull %3) #9
  ret i32 %13
}

; Function Attrs: mustprogress nocallback nofree nosync nounwind willreturn memory(argmem: readwrite)
declare void @llvm.lifetime.start.p0(i64 immarg, ptr nocapture) #6

; Function Attrs: mustprogress nofree noinline norecurse nosync nounwind ssp willreturn memory(argmem: readwrite) uwtable(sync)
define internal fastcc void @copy_pointers(ptr nocapture noundef writeonly %0, ptr nocapture noundef readonly %1) unnamed_addr #7 {
  tail call void @llvm.memcpy.p0.p0.i64(ptr noundef nonnull align 8 dereferenceable(16) %0, ptr noundef nonnull align 8 dereferenceable(16) %1, i64 16, i1 false)
  ret void
}

; Function Attrs: mustprogress nocallback nofree nosync nounwind willreturn memory(argmem: readwrite)
declare void @llvm.lifetime.end.p0(i64 immarg, ptr nocapture) #6

; Function Attrs: mustprogress nocallback nofree nounwind willreturn memory(argmem: readwrite)
declare void @llvm.memcpy.p0.p0.i64(ptr noalias nocapture writeonly, ptr noalias nocapture readonly, i64, i1 immarg) #8

attributes #0 = { mustprogress nofree norecurse nosync nounwind ssp willreturn memory(none) uwtable(sync) "frame-pointer"="non-leaf" "no-trapping-math"="true" "probe-stack"="__chkstk_darwin" "stack-protector-buffer-size"="8" "target-cpu"="apple-m1" "target-features"="+aes,+altnzcv,+bti,+ccdp,+ccidx,+complxnum,+crc,+dit,+dotprod,+flagm,+fp-armv8,+fp16fml,+fptoint,+fullfp16,+jsconv,+lse,+neon,+pauth,+perfmon,+predres,+ras,+rcpc,+rdm,+sb,+sha2,+sha3,+specrestrict,+ssbs,+v8.1a,+v8.2a,+v8.3a,+v8.4a,+v8.5a,+v8a,+zcm,+zcz" }
attributes #1 = { mustprogress nocallback nofree nosync nounwind speculatable willreturn memory(none) }
attributes #2 = { mustprogress nofree norecurse nosync nounwind ssp willreturn memory(readwrite, inaccessiblemem: none) uwtable(sync) "frame-pointer"="non-leaf" "no-trapping-math"="true" "probe-stack"="__chkstk_darwin" "stack-protector-buffer-size"="8" "target-cpu"="apple-m1" "target-features"="+aes,+altnzcv,+bti,+ccdp,+ccidx,+complxnum,+crc,+dit,+dotprod,+flagm,+fp-armv8,+fp16fml,+fptoint,+fullfp16,+jsconv,+lse,+neon,+pauth,+perfmon,+predres,+ras,+rcpc,+rdm,+sb,+sha2,+sha3,+specrestrict,+ssbs,+v8.1a,+v8.2a,+v8.3a,+v8.4a,+v8.5a,+v8a,+zcm,+zcz" }
attributes #3 = { mustprogress nofree noinline norecurse nosync nounwind ssp willreturn memory(readwrite, argmem: none, inaccessiblemem: none) uwtable(sync) "frame-pointer"="non-leaf" "no-trapping-math"="true" "probe-stack"="__chkstk_darwin" "stack-protector-buffer-size"="8" "target-cpu"="apple-m1" "target-features"="+aes,+altnzcv,+bti,+ccdp,+ccidx,+complxnum,+crc,+dit,+dotprod,+flagm,+fp-armv8,+fp16fml,+fptoint,+fullfp16,+jsconv,+lse,+neon,+pauth,+perfmon,+predres,+ras,+rcpc,+rdm,+sb,+sha2,+sha3,+specrestrict,+ssbs,+v8.1a,+v8.2a,+v8.3a,+v8.4a,+v8.5a,+v8a,+zcm,+zcz" }
attributes #4 = { mustprogress nofree norecurse nosync nounwind ssp willreturn memory(write, argmem: none, inaccessiblemem: none) uwtable(sync) "frame-pointer"="non-leaf" "no-trapping-math"="true" "probe-stack"="__chkstk_darwin" "stack-protector-buffer-size"="8" "target-cpu"="apple-m1" "target-features"="+aes,+altnzcv,+bti,+ccdp,+ccidx,+complxnum,+crc,+dit,+dotprod,+flagm,+fp-armv8,+fp16fml,+fptoint,+fullfp16,+jsconv,+lse,+neon,+pauth,+perfmon,+predres,+ras,+rcpc,+rdm,+sb,+sha2,+sha3,+specrestrict,+ssbs,+v8.1a,+v8.2a,+v8.3a,+v8.4a,+v8.5a,+v8a,+zcm,+zcz" }
attributes #5 = { mustprogress nofree norecurse nosync nounwind ssp willreturn memory(read, inaccessiblemem: none) uwtable(sync) "frame-pointer"="non-leaf" "no-trapping-math"="true" "probe-stack"="__chkstk_darwin" "stack-protector-buffer-size"="8" "target-cpu"="apple-m1" "target-features"="+aes,+altnzcv,+bti,+ccdp,+ccidx,+complxnum,+crc,+dit,+dotprod,+flagm,+fp-armv8,+fp16fml,+fptoint,+fullfp16,+jsconv,+lse,+neon,+pauth,+perfmon,+predres,+ras,+rcpc,+rdm,+sb,+sha2,+sha3,+specrestrict,+ssbs,+v8.1a,+v8.2a,+v8.3a,+v8.4a,+v8.5a,+v8a,+zcm,+zcz" }
attributes #6 = { mustprogress nocallback nofree nosync nounwind willreturn memory(argmem: readwrite) }
attributes #7 = { mustprogress nofree noinline norecurse nosync nounwind ssp willreturn memory(argmem: readwrite) uwtable(sync) "frame-pointer"="non-leaf" "no-trapping-math"="true" "probe-stack"="__chkstk_darwin" "stack-protector-buffer-size"="8" "target-cpu"="apple-m1" "target-features"="+aes,+altnzcv,+bti,+ccdp,+ccidx,+complxnum,+crc,+dit,+dotprod,+flagm,+fp-armv8,+fp16fml,+fptoint,+fullfp16,+jsconv,+lse,+neon,+pauth,+perfmon,+predres,+ras,+rcpc,+rdm,+sb,+sha2,+sha3,+specrestrict,+ssbs,+v8.1a,+v8.2a,+v8.3a,+v8.4a,+v8.5a,+v8a,+zcm,+zcz" }
attributes #8 = { mustprogress nocallback nofree nounwind willreturn memory(argmem: readwrite) }
attributes #9 = { nounwind }

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
