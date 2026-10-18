module alu(input [7:0] a, b, input [1:0] op,
           output [7:0] y, output equal, less);
  wire [7:0] added, masked, shifted;
  assign added = a + b;
  assign masked = a ^ b;
  assign shifted = a << b;
  assign y = op == 2'd0 ? added :
             op == 2'd1 ? a - b :
             op == 2'd2 ? masked : shifted;
  assign equal = a == b;
  assign less = a < b;
endmodule
