// Copyright 2026 Michael Brackx
// SPDX-License-Identifier: Apache-2.0
module division(input signed [7:0] dividend, divisor,
                output signed [7:0] quotient, remainder,
                output [7:0] unsigned_q, unsigned_r);
  // Quotients truncate toward zero; signed remainders follow the dividend.
  assign quotient = dividend / divisor;
  assign remainder = dividend % divisor;
  assign unsigned_q = $unsigned(dividend) / $unsigned(divisor);
  assign unsigned_r = $unsigned(dividend) % $unsigned(divisor);
endmodule
