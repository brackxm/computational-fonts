// Copyright 2026 Michael Brackx
// SPDX-License-Identifier: Apache-2.0
module signed_math(input signed [7:0] a, b,
                   input [3:0] shift,
                   output signed [8:0] sum,
                   output signed [15:0] product,
                   output signed [7:0] shifted,
                   output less);
  assign sum = a + b;
  assign product = a * b;
  assign shifted = a >>> shift;
  assign less = a < b;
endmodule
