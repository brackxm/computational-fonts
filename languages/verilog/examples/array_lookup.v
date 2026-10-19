// A pure function expands to local combinational array words and a selector.
module array_lookup(input [7:0] a, b, input [2:0] index, output [7:0] y);
  function [7:0] lookup(input [7:0] x, z, input [2:0] address);
    reg [7:0] words[0:3];
    begin
      words[0] = x;
      words[1] = z;
      words[2] = x ^ z;
      words[3] = ~x;
      lookup = words[address];
    end
  endfunction
  assign y = lookup(a, b, index);
endmodule
