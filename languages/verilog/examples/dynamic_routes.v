// Copyright 2026 Michael Brackx
// SPDX-License-Identifier: Apache-2.0
module dynamic_routes(input [7:0] data, input [3:0] index, input [2:0] value,
                      output selected, output reg [2:0] window,
                      output reg [7:0] patched);
  // An index above 7 would produce X and is reported as an execution error.
  assign selected = data[index];
  always @* begin
    window = 0;
    if (index <= 5) window = data[index +: 3];
    patched = data;
    patched[index +: 3] = value;
  end
endmodule
