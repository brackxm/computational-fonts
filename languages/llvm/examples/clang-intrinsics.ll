; ModuleID = 'languages/llvm/examples/intrinsics.c'
source_filename = "languages/llvm/examples/intrinsics.c"
target datalayout = "e-m:o-i64:64-i128:128-n32:64-S128-Fn32"
target triple = "arm64-apple-macosx15.0.0"

@__const.copied_array.cells = private unnamed_addr constant [4 x i32] [i32 3, i32 5, i32 7, i32 11], align 4

; Function Attrs: mustprogress nofree norecurse nosync nounwind ssp willreturn memory(none) uwtable(sync)
define i32 @constant_lookup(i32 noundef %0) local_unnamed_addr #0 {
  %2 = and i32 %0, 3
  %3 = zext nneg i32 %2 to i64
  %4 = getelementptr inbounds [4 x i32], ptr @__const.copied_array.cells, i64 0, i64 %3
  %5 = load i32, ptr %4, align 4, !tbaa !6
  ret i32 %5
}

; Function Attrs: mustprogress nofree norecurse nosync nounwind ssp willreturn memory(none) uwtable(sync)
define i32 @copied_array(i32 noundef %0, i32 noundef %1) local_unnamed_addr #0 {
  %3 = alloca [4 x i32], align 4
  call void @llvm.lifetime.start.p0(i64 16, ptr nonnull %3) #4
  call void @llvm.memcpy.p0.p0.i64(ptr noundef nonnull align 4 dereferenceable(16) %3, ptr noundef nonnull align 4 dereferenceable(16) @__const.copied_array.cells, i64 16, i1 false)
  %4 = and i32 %0, 3
  %5 = zext nneg i32 %4 to i64
  %6 = getelementptr inbounds [4 x i32], ptr %3, i64 0, i64 %5
  %7 = load i32, ptr %6, align 4, !tbaa !6
  %8 = xor i32 %7, %1
  store i32 %8, ptr %6, align 4, !tbaa !6
  %9 = add i32 %0, 1
  %10 = and i32 %9, 3
  %11 = zext nneg i32 %10 to i64
  %12 = getelementptr inbounds [4 x i32], ptr %3, i64 0, i64 %11
  %13 = load i32, ptr %12, align 4, !tbaa !6
  %14 = add i32 %13, %8
  call void @llvm.lifetime.end.p0(i64 16, ptr nonnull %3) #4
  ret i32 %14
}

; Function Attrs: mustprogress nocallback nofree nosync nounwind willreturn memory(argmem: readwrite)
declare void @llvm.lifetime.start.p0(i64 immarg, ptr nocapture) #1

; Function Attrs: mustprogress nocallback nofree nounwind willreturn memory(argmem: readwrite)
declare void @llvm.memcpy.p0.p0.i64(ptr noalias nocapture writeonly, ptr noalias nocapture readonly, i64, i1 immarg) #2

; Function Attrs: mustprogress nocallback nofree nosync nounwind willreturn memory(argmem: readwrite)
declare void @llvm.lifetime.end.p0(i64 immarg, ptr nocapture) #1

; Function Attrs: mustprogress nofree norecurse nosync nounwind ssp willreturn memory(none) uwtable(sync)
define range(i64 0, 8589934592) i64 @checked_add(i32 noundef %0, i32 noundef %1) local_unnamed_addr #0 {
  %3 = tail call { i32, i1 } @llvm.uadd.with.overflow.i32(i32 %0, i32 %1)
  %4 = extractvalue { i32, i1 } %3, 1
  %5 = extractvalue { i32, i1 } %3, 0
  %6 = zext i32 %5 to i64
  %7 = select i1 %4, i64 4294967296, i64 0
  %8 = or disjoint i64 %7, %6
  ret i64 %8
}

; Function Attrs: mustprogress nocallback nofree nosync nounwind speculatable willreturn memory(none)
declare { i32, i1 } @llvm.uadd.with.overflow.i32(i32, i32) #3

; Function Attrs: mustprogress nofree norecurse nosync nounwind ssp willreturn memory(none) uwtable(sync)
define range(i64 0, 8589934592) i64 @checked_multiply(i32 noundef %0, i32 noundef %1) local_unnamed_addr #0 {
  %3 = tail call { i32, i1 } @llvm.smul.with.overflow.i32(i32 %0, i32 %1)
  %4 = extractvalue { i32, i1 } %3, 1
  %5 = extractvalue { i32, i1 } %3, 0
  %6 = zext i32 %5 to i64
  %7 = select i1 %4, i64 4294967296, i64 0
  %8 = or disjoint i64 %7, %6
  ret i64 %8
}

; Function Attrs: mustprogress nocallback nofree nosync nounwind speculatable willreturn memory(none)
declare { i32, i1 } @llvm.smul.with.overflow.i32(i32, i32) #3

attributes #0 = { mustprogress nofree norecurse nosync nounwind ssp willreturn memory(none) uwtable(sync) "frame-pointer"="non-leaf" "no-trapping-math"="true" "probe-stack"="__chkstk_darwin" "stack-protector-buffer-size"="8" "target-cpu"="apple-m1" "target-features"="+aes,+altnzcv,+bti,+ccdp,+ccidx,+complxnum,+crc,+dit,+dotprod,+flagm,+fp-armv8,+fp16fml,+fptoint,+fullfp16,+jsconv,+lse,+neon,+pauth,+perfmon,+predres,+ras,+rcpc,+rdm,+sb,+sha2,+sha3,+specrestrict,+ssbs,+v8.1a,+v8.2a,+v8.3a,+v8.4a,+v8.5a,+v8a,+zcm,+zcz" }
attributes #1 = { mustprogress nocallback nofree nosync nounwind willreturn memory(argmem: readwrite) }
attributes #2 = { mustprogress nocallback nofree nounwind willreturn memory(argmem: readwrite) }
attributes #3 = { mustprogress nocallback nofree nosync nounwind speculatable willreturn memory(none) }
attributes #4 = { nounwind }

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
