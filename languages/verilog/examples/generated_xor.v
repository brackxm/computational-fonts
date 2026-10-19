// Each generated lane instantiates a cell with its own input/output wires.
module generated_xor #(parameter WIDTH = 8)(
  input [WIDTH-1:0] a, b, output [WIDTH-1:0] y
);
  genvar g;
  generate
    for (g = 0; g < WIDTH; g = g + 1) begin: lanes
      xor_cell u(.a(a[g]), .b(b[g]), .y(y[g]));
    end
  endgenerate
endmodule

module xor_cell(input a, b, output y);
  assign y = a ^ b;
endmodule
