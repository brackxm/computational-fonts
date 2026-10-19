// Copyright 2026 Michael Brackx
// SPDX-License-Identifier: Apache-2.0
module hierarchical_adder(input [7:0] a, b, output [8:0] sum);
  wire carry;
  adder_cell #(.WIDTH(4)) low(.a(a[3:0]), .b(b[3:0]), .cin(1'b0),
                             .sum(sum[3:0]), .cout(carry));
  adder_cell #(.WIDTH(4)) high(.a(a[7:4]), .b(b[7:4]), .cin(carry),
                              .sum(sum[7:4]), .cout(sum[8]));
endmodule

module adder_cell #(parameter WIDTH = 4)(input [WIDTH-1:0] a, b, input cin,
                                        output [WIDTH-1:0] sum, output cout);
  wire [WIDTH:0] total = a + b + cin;
  assign sum = total[WIDTH-1:0];
  assign cout = total[WIDTH];
endmodule
