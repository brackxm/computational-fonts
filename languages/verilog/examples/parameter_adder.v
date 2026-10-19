// Build with -P WIDTH=16 to specialize the same circuit to wider input ports.
module parameter_adder #(
  parameter WIDTH = 8,
  parameter [WIDTH-1:0] MASK = 8'hA5
)(input [WIDTH-1:0] a, b,
  output [WIDTH:0] sum,
  output [WIDTH-1:0] masked, toggled);
  localparam [WIDTH-1:0] TOP_BIT = 1'b1 << (WIDTH-1);
  wire [WIDTH-1:0] mixed = a ^ b, filtered = mixed & MASK;
  assign sum = a + b;
  assign masked = filtered;
  assign toggled = a ^ TOP_BIT;
endmodule
