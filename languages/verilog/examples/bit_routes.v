module bit_routes(input [7:0] data, input enable,
                  output [7:0] swapped, masked, output parity, all_set);
  assign swapped = {data[3:0], data[7:4]};
  assign masked = data & {8{enable}};
  assign parity = ^data;
  assign all_set = &data;
endmodule
