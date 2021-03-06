/** @copyright (C) 2016-2017,  Gavin J Stark.  All rights reserved.
 *
 * @copyright
 *    Licensed under the Apache License, Version 2.0 (the "License");
 *    you may not use this file except in compliance with the License.
 *    You may obtain a copy of the License at
 *     http://www.apache.org/licenses/LICENSE-2.0.
 *   Unless required by applicable law or agreed to in writing, software
 *   distributed under the License is distributed on an "AS IS" BASIS,
 *   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 *   See the License for the specific language governing permissions and
 *   limitations under the License.
 *
 * @file   framebuffer.h
 * @brief  Framebuffer CDL types and submodules
 *
 * Header file for framebuffer modules for VGA, LCD panel, both
 * bitmapped and teletext.
 *
 */

/*a Includes */
include "csr_interface.h"
include "teletext.h"
include "bbc_micro_types.h"

/*a Types */
/*t t_video_timing
 *
 * Timing controls from a framebuffer_timing module, to control a
 * framebuffer video driver
 */
typedef struct {
    bit v_sync              "Asserted for the whole of the first scanline or a frame";
    bit h_sync              "Asserted for a single clock at the start of every scanline";
    bit will_h_sync         "Asserted if the next clock will be an @a h_sync";
    bit v_displaying        "Asserted for a scanline if the scanline will display data";
    bit display_required    "Asserted for scanlines being displayed, up to the end of the horizontal displayed area - permits prefetching of pixel data";
    bit will_display_enable "Asserted if the next clock will have @a display_enable asserted";
    bit display_enable      "Asserted if pixels should be presented to the output (i.e. outside the front and back porches both horizontally and vertically)";
} t_video_timing;

/*a Modules */
/*m framebuffer_timing */
extern
module framebuffer_timing( clock csr_clk                      "Clock for CSR reads/writes",
                           clock video_clk                    "Video clock, used to generate vsync, hsync, data out, etc",
                           input bit reset_n                  "Active low reset",
                           output t_video_timing video_timing "Video timing outputs",
                           input t_csr_request csr_request    "Pipelined CSR request interface to control the module",
                           output t_csr_response csr_response "Pipelined CSR response interface to control the module",
                           input bit[16] csr_select           "CSR select value to target this module on the CSR interface"
    )
{
    timing from rising clock video_clk video_timing;

    timing to   rising clock csr_clk csr_request, csr_select;
    timing from rising clock csr_clk csr_response;
}

/*m framebuffer_teletext */
extern
module framebuffer_teletext( clock csr_clk "Clock for CSR reads/writes",
                             clock sram_clk  "SRAM write clock, with frame buffer data",
                             clock video_clk "Video clock, used to generate vsync, hsync, data out, etc",
                             input bit reset_n,
                             input t_bbc_display_sram_write display_sram_write,
                             output t_video_bus video_bus,
                             input t_csr_request csr_request,
                             output t_csr_response csr_response
    )
{
    timing to   rising clock sram_clk   display_sram_write;
    timing to   rising clock csr_clk    csr_request;
    timing from rising clock csr_clk    csr_response;
    timing from rising clock video_clk  video_bus;
}

/*m framebuffer */
extern
module framebuffer( clock csr_clk "Clock for CSR reads/writes",
                    clock sram_clk  "SRAM write clock, with frame buffer data",
                    clock video_clk "Video clock, used to generate vsync, hsync, data out, etc",
                    input bit reset_n,
                    input t_bbc_display_sram_write display_sram_write,
                    output t_video_bus video_bus,
                    input t_csr_request csr_request,
                    output t_csr_response csr_response,
                    input bit[16] csr_select           "CSR select value to target this module on the CSR interface"
    )
{
    timing to   rising clock sram_clk   display_sram_write;
    timing to   rising clock csr_clk    csr_request, csr_select;
    timing from rising clock csr_clk    csr_response;
    timing from rising clock video_clk  video_bus;
}

