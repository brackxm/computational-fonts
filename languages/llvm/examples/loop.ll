define i32 @sum(i32 %n) {
entry:
  br label %loop
loop:
  %i = phi i32 [0, %entry], [%next, %body]
  %sum = phi i32 [0, %entry], [%added, %body]
  %more = icmp ult i32 %i, %n
  br i1 %more, label %body, label %exit
body:
  %added = add i32 %sum, %i
  %next = add i32 %i, 1
  br label %loop
exit:
  ret i32 %sum
}
