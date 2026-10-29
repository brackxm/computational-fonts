define i32 @max(i32 %a, i32 %b) {
entry:
  %cmp = icmp sgt i32 %a, %b
  %result = select i1 %cmp, i32 %a, i32 %b
  ret i32 %result
}
