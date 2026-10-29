; ModuleID = 'languages/llvm/examples/abi.c'
source_filename = "languages/llvm/examples/abi.c"
target datalayout = "e-m:o-i64:64-i128:128-n32:64-S128-Fn32"
target triple = "arm64-apple-macosx15.0.0"

%struct.Triple = type { i64, i64, i64 }

@makers = internal unnamed_addr constant [2 x ptr] [ptr @make_triple, ptr @reverse_triple], align 8

; Function Attrs: mustprogress nofree noinline norecurse nosync nounwind ssp willreturn memory(argmem: write) uwtable(sync)
define void @make_triple(ptr dead_on_unwind noalias nocapture writable writeonly sret(%struct.Triple) align 8 %0, i64 noundef %1, i64 noundef %2) #0 {
  %4 = add i64 %2, %1
  store i64 %4, ptr %0, align 8, !tbaa !6
  %5 = getelementptr inbounds i8, ptr %0, i64 8
  %6 = xor i64 %2, %1
  store i64 %6, ptr %5, align 8, !tbaa !11
  %7 = getelementptr inbounds i8, ptr %0, i64 16
  %8 = sub i64 %1, %2
  store i64 %8, ptr %7, align 8, !tbaa !12
  ret void
}

; Function Attrs: mustprogress nofree noinline norecurse nosync nounwind ssp willreturn memory(argmem: write) uwtable(sync)
define void @reverse_triple(ptr dead_on_unwind noalias nocapture writable writeonly sret(%struct.Triple) align 8 %0, i64 noundef %1, i64 noundef %2) #0 {
  tail call void @make_triple(ptr dead_on_unwind writable sret(%struct.Triple) align 8 %0, i64 noundef %2, i64 noundef %1)
  ret void
}

; Function Attrs: mustprogress nofree noinline norecurse nosync nounwind ssp willreturn memory(argmem: readwrite) uwtable(sync)
define i64 @use_triple(ptr nocapture noundef %0) local_unnamed_addr #1 {
  %2 = load i64, ptr %0, align 8, !tbaa !6
  %3 = add i64 %2, 7
  store i64 %3, ptr %0, align 8, !tbaa !6
  %4 = getelementptr inbounds i8, ptr %0, i64 8
  %5 = load i64, ptr %4, align 8, !tbaa !11
  %6 = getelementptr inbounds i8, ptr %0, i64 16
  %7 = load i64, ptr %6, align 8, !tbaa !12
  %8 = xor i64 %5, %7
  %9 = xor i64 %8, %3
  ret i64 %9
}

; Function Attrs: mustprogress nofree norecurse nosync nounwind ssp willreturn memory(none) uwtable(sync)
define i64 @call_triple(i64 noundef %0, i64 noundef %1) local_unnamed_addr #2 {
  %3 = alloca %struct.Triple, align 8
  call void @llvm.lifetime.start.p0(i64 24, ptr nonnull %3) #5
  call void @make_triple(ptr dead_on_unwind nonnull writable sret(%struct.Triple) align 8 %3, i64 noundef %0, i64 noundef %1)
  %4 = call i64 @use_triple(ptr noundef nonnull %3)
  call void @llvm.lifetime.end.p0(i64 24, ptr nonnull %3) #5
  ret i64 %4
}

; Function Attrs: mustprogress nocallback nofree nosync nounwind willreturn memory(argmem: readwrite)
declare void @llvm.lifetime.start.p0(i64 immarg, ptr nocapture) #3

; Function Attrs: mustprogress nocallback nofree nosync nounwind willreturn memory(argmem: readwrite)
declare void @llvm.lifetime.end.p0(i64 immarg, ptr nocapture) #3

; Function Attrs: nounwind ssp uwtable(sync)
define void @choose_triple(ptr dead_on_unwind noalias writable sret(%struct.Triple) align 8 %0, i32 noundef %1, i64 noundef %2, i64 noundef %3) local_unnamed_addr #4 {
  %5 = and i32 %1, 1
  %6 = zext nneg i32 %5 to i64
  %7 = getelementptr inbounds [2 x ptr], ptr @makers, i64 0, i64 %6
  %8 = load ptr, ptr %7, align 8, !tbaa !13
  tail call void %8(ptr dead_on_unwind writable sret(%struct.Triple) align 8 %0, i64 noundef %2, i64 noundef %3) #5
  ret void
}

attributes #0 = { mustprogress nofree noinline norecurse nosync nounwind ssp willreturn memory(argmem: write) uwtable(sync) "frame-pointer"="non-leaf" "no-trapping-math"="true" "probe-stack"="__chkstk_darwin" "stack-protector-buffer-size"="8" "target-cpu"="apple-m1" "target-features"="+aes,+altnzcv,+bti,+ccdp,+ccidx,+complxnum,+crc,+dit,+dotprod,+flagm,+fp-armv8,+fp16fml,+fptoint,+fullfp16,+jsconv,+lse,+neon,+pauth,+perfmon,+predres,+ras,+rcpc,+rdm,+sb,+sha2,+sha3,+specrestrict,+ssbs,+v8.1a,+v8.2a,+v8.3a,+v8.4a,+v8.5a,+v8a,+zcm,+zcz" }
attributes #1 = { mustprogress nofree noinline norecurse nosync nounwind ssp willreturn memory(argmem: readwrite) uwtable(sync) "frame-pointer"="non-leaf" "no-trapping-math"="true" "probe-stack"="__chkstk_darwin" "stack-protector-buffer-size"="8" "target-cpu"="apple-m1" "target-features"="+aes,+altnzcv,+bti,+ccdp,+ccidx,+complxnum,+crc,+dit,+dotprod,+flagm,+fp-armv8,+fp16fml,+fptoint,+fullfp16,+jsconv,+lse,+neon,+pauth,+perfmon,+predres,+ras,+rcpc,+rdm,+sb,+sha2,+sha3,+specrestrict,+ssbs,+v8.1a,+v8.2a,+v8.3a,+v8.4a,+v8.5a,+v8a,+zcm,+zcz" }
attributes #2 = { mustprogress nofree norecurse nosync nounwind ssp willreturn memory(none) uwtable(sync) "frame-pointer"="non-leaf" "no-trapping-math"="true" "probe-stack"="__chkstk_darwin" "stack-protector-buffer-size"="8" "target-cpu"="apple-m1" "target-features"="+aes,+altnzcv,+bti,+ccdp,+ccidx,+complxnum,+crc,+dit,+dotprod,+flagm,+fp-armv8,+fp16fml,+fptoint,+fullfp16,+jsconv,+lse,+neon,+pauth,+perfmon,+predres,+ras,+rcpc,+rdm,+sb,+sha2,+sha3,+specrestrict,+ssbs,+v8.1a,+v8.2a,+v8.3a,+v8.4a,+v8.5a,+v8a,+zcm,+zcz" }
attributes #3 = { mustprogress nocallback nofree nosync nounwind willreturn memory(argmem: readwrite) }
attributes #4 = { nounwind ssp uwtable(sync) "frame-pointer"="non-leaf" "no-trapping-math"="true" "probe-stack"="__chkstk_darwin" "stack-protector-buffer-size"="8" "target-cpu"="apple-m1" "target-features"="+aes,+altnzcv,+bti,+ccdp,+ccidx,+complxnum,+crc,+dit,+dotprod,+flagm,+fp-armv8,+fp16fml,+fptoint,+fullfp16,+jsconv,+lse,+neon,+pauth,+perfmon,+predres,+ras,+rcpc,+rdm,+sb,+sha2,+sha3,+specrestrict,+ssbs,+v8.1a,+v8.2a,+v8.3a,+v8.4a,+v8.5a,+v8a,+zcm,+zcz" }
attributes #5 = { nounwind }

!llvm.module.flags = !{!0, !1, !2, !3, !4}
!llvm.ident = !{!5}

!0 = !{i32 2, !"SDK Version", [2 x i32] [i32 26, i32 2]}
!1 = !{i32 1, !"wchar_size", i32 4}
!2 = !{i32 8, !"PIC Level", i32 2}
!3 = !{i32 7, !"uwtable", i32 1}
!4 = !{i32 7, !"frame-pointer", i32 1}
!5 = !{!"Apple clang version 17.0.0 (clang-1700.6.4.2)"}
!6 = !{!7, !8, i64 0}
!7 = !{!"", !8, i64 0, !8, i64 8, !8, i64 16}
!8 = !{!"long long", !9, i64 0}
!9 = !{!"omnipotent char", !10, i64 0}
!10 = !{!"Simple C/C++ TBAA"}
!11 = !{!7, !8, i64 8}
!12 = !{!7, !8, i64 16}
!13 = !{!14, !14, i64 0}
!14 = !{!"any pointer", !9, i64 0}
