// Original experimental v3 AArch64 wrapper, assembled at VA 0x71600.
// This is NOT a generic camera patch. Builder pins both firmware binaries.
// Controlled native DV, SDR transition, and module Action checks passed.
// Test automation must release the camera client gracefully before force-stop;
// abrupt termination also reproduced lifecycle failures without instrumentation.
// This source does not imply a production-ready or automatic-install release.
// v3 widens only motion guard constants; 360 synthetic transforms passed.
// Physical motion/rolling-shutter behavior remains unvalidated.
// Incoming: x0 engine, w1/w2 full size, w3/w4 window, x5 source grid,
// x6 destination grid. There are no FP or stack arguments at verified callers.
// Guard uses only x8-x17 and v0-v7 (caller-saved); original arguments stay intact.
// Original entry PACIASP is PRESERVED (also a BTI-compatible landing).
// The instruction at entry+4 is replaced by B shim.
// .Loriginal executes displaced STP then branches to entry+8; its incoming LR
// is already signed. .Lcall_original signs the new nested-call LR first.
// HINT encodings below are the architectural PACIASP/AUTIASP/BTI C aliases.

    hint #34                    // BTI C
    cbz x0, .Loriginal
    cbz x5, .Loriginal
    cmp w1, #4000
    b.ne .Loriginal
    cmp w2, #2250
    b.ne .Loriginal
    cmp w3, #3840
    b.ne .Loriginal
    cmp w4, #2160
    b.ne .Loriginal
    ldr w8, [x0, #0x240]         // EISMode: 2 = SAT_EIS_60FPS
    cmp w8, #2
    b.ne .Loriginal
    ldr x8, [x0, #0x2a8]         // ExtensionPluginBase*
    cbz x8, .Loriginal
    ldr w8, [x8, #0x88]          // Exact pinned IsDolbyVideoMode predicate
    cmp w8, #30
    b.eq .Lfinite
    cmp w8, #33
    b.ne .Loriginal
.Lfinite:
    mov x8, x5
    mov w9, #825
    mov w11, #0x7f800000         // Float exponent mask: reject Inf/NaN
    ldr s4, .LpositiveInfinity
    ldr s5, .LnegativeInfinity
.Lscan:
    ldp w12, w13, [x8], #8
    and w14, w12, w11
    cmp w14, w11
    b.eq .Loriginal
    and w14, w13, w11
    cmp w14, w11
    b.eq .Loriginal
    fmov s0, w13
    fmin s4, s4, s0
    fmax s5, s5, s0
    subs w9, w9, #1
    b.ne .Lscan
    ldr s0, .LminYLower
    fcmp s4, s0
    b.lo .Loriginal
    ldr s0, .LminYUpper
    fcmp s4, s0
    b.hi .Loriginal
    ldr s0, .LmaxYLower
    fcmp s5, s0
    b.lo .Loriginal
    ldr s0, .LmaxYUpper
    fcmp s5, s0
    b.hi .Loriginal
    ldr s0, [x5, #3296]          // Center point 412: X
    ldr s1, .LcenterXLower
    fcmp s0, s1
    b.lo .Loriginal
    ldr s1, .LcenterXUpper
    fcmp s0, s1
    b.hi .Loriginal
    ldr s0, [x5, #3300]          // Center point 412: Y
    ldr s1, .LcenterYLower
    fcmp s0, s1
    b.lo .Loriginal
    ldr s1, .LcenterYUpper
    fcmp s0, s1
    b.hi .Loriginal

    // Accepted. Caller LR is ALREADY signed by preserved original PACIASP.
    // Preserve caller LR and x29, then allocate a private grid.
    // 16-byte frame + 6608-byte allocation; SP stays 16-byte aligned.
    stp x29, x30, [sp, #-16]!
    mov x29, sp
    sub sp, sp, #1, lsl #12
    sub sp, sp, #0x9d0           // 4096 + 2512 = 6608
    mov x8, x5
    mov x9, sp
    mov w10, #825
    ldr s1, .LyDelta
.Lcopy:
    ldr w11, [x8]
    ldr s0, [x8, #4]
    fadd s0, s0, s1
    str w11, [x9]
    str s0, [x9, #4]
    add x8, x8, #8
    add x9, x9, #8
    subs w10, w10, #1
    b.ne .Lcopy
    mov x5, sp
    bl .Lcall_original          // Nested LR needs its own PACIASP
    add sp, sp, #0x9d0
    add sp, sp, #1, lsl #12
    ldp x29, x30, [sp], #16
    hint #29                    // AUTIASP: entry SP restored
    ret

.Lcall_original:
    hint #25                    // Sign fresh nested-call LR using nested SP
.Loriginal:
    stp d11, d10, [sp, #-0x80]!  // Displaced original instruction at entry+4
    b __ORIGINAL_PLUS8__

    .align 2
.LpositiveInfinity: .word 0x7f800000
.LnegativeInfinity: .word 0xff800000
.LminYLower:        .word 0xc3fa0000   // -500
.LminYUpper:        .word 0xc37a0000   // -250
.LmaxYLower:        .word 0x44d48000   // 1700
.LmaxYUpper:        .word 0x45002000   // 2050
.LcenterXLower:     .word 0x44ed8000   // 1900
.LcenterXUpper:     .word 0x45034000   // 2100
.LcenterYLower:     .word 0x44228000   // 650
.LcenterYUpper:     .word 0x44548000   // 850
.LyDelta:           .word 0x43bb8000   // 375, tested firmware domain hypothesis
