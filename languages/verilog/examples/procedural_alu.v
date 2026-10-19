// Copyright 2026 Michael Brackx
// SPDX-License-Identifier: Apache-2.0
module procedural_alu(input [7:0] a, b, input [1:0] op,
                      output reg [8:0] y);
  always @* begin
    y = 0;
    case (op)
      0: y = a + b;
      1: begin
        y = a - b;
        if (a < b) y[8] = 1'b1;
      end
      2: y = a ^ b;
      default: y = {a[3:0], b[3:0]};
    endcase
  end
endmodule
