// Count the set bits with eight blocking additions, unrolled at compilation.
module population_count(input [7:0] data, output reg [3:0] count);
  integer i;
  always @* begin
    count = 0;
    for (i = 0; i < 8; i = i + 1)
      count = count + data[i];
  end
endmodule
