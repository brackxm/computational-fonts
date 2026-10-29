%Pair = type { i8, [4 x i32] }
define i32 @memory(i32 %index, i32 %value) {
entry:
  %p = alloca %Pair, align 8
  %bounded = and i32 %index, 3
  %cell = getelementptr inbounds %Pair, ptr %p, i64 0, i32 1, i32 %bounded
  store i32 %value, ptr %cell, align 4
  %v = load i32, ptr %cell, align 4
  ret i32 %v
}
