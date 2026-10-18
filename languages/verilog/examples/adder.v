// Assignment context preserves the carry in the nine-bit output.
module adder(input [7:0] a, b, output [8:0] sum);
  assign sum = a + b;
endmodule
