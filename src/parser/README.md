# WPILOG File Basics

A .wpilog file consists of two basic parts

1. a 12 byte header (possibly longer, if specified)
2. a stream of "records" back to back to back

## File Header Breakdown

The header can be broken down into three parts

1. an ASCII magic string, in this case "WPILOG"
2. a log version number
3. a 4 byte uint32 giving the length of an optional extra header string

You can see this breakdown as follows
```
 57 50 49 4c 4f 47    00 01    00 00 00 00
└────"WPILOG" ────┘  └ ver ┘  └─extra hdr─┘
```

In most cases the exta header will not exist, so the first record will begin immediately after the 12th header byte. Something to notice here is that the file is stored in little-endian. The bits `00 01` are read into python as `0x0100`, which corresponds to version 1.0. This reversal is only true for numbers stored across multiple bytes. Notice that individual characters of WPILOG are stored in the correct order. 

## Record Breakdown

The records follow a similar pattern. Each record can be broken down into two main parts.

1. a small but variable length header containing basic information about the payload
2. the payload itself, with a length defined by the header

### Record Header Breakdown

The header of the payload consists of four main parts

1. a header-length bitfield that determines the lengths of the other fields in the header.
2. an entry ID
3. a payload size/length
4. a timestamp length

Consider the below record header
```
20   00   1e   4d 1d 1a   
│    │    │   └timestamp┘
│    │    └ payload size
│    └ entry ID
└ variable header-length bitfield
```
The byte `0x20` is actually a bitfield that is decoded into three slices. Each slice represents the length of the header field that contains critical information about the record.
1. the lowest two bits contain the number of bytes that store the record entry ID
2. the next two bits are the number of bytes that store the payload length
3. the highest four bits contain the number of bytes that store the timestamp length

Each one of these values is stored minus one. Now consider the record header above and notice that `0x20` is equivalent to `0b0010_0000` then

1. the low two bits are `00` so the entry ID is 0+1 = 1 byte
2. the next two bits are `00` payload size is stored in 0+1 = 1 byte
3. the high four bits are `0010` so the timestamp is stored in 2+1 = 3 bytes

Notice we can now calculate the header length as the sum total number of bytes of all of the header fields including the heater length byte. In this case the header is 1 + 1 + 1 + 3 = 6 bytes. This means the payload starts on the 7th byte and is of length `0x1e`.

A quick note about the timestamp - it is stored little endian so `4d 1d 1a` is equivalent to `0x1a1d4d`.

### Record Payload Breakdown

```
00              control type = 0 (Start)                     [1 byte]
02 00 00 00     entry ID = 2                                 [4 bytes, uint32]
07 00 00 00     name length = 7                              [4 bytes, uint32]
63 6f 6e 73 6f 6c 65   "console"                             [7 bytes]
06 00 00 00     type length = 6                              [4 bytes, uint32]
73 74 72 69 6e 67       "string"                             [6 bytes]
00 00 00 00     metadata length = 0                          [4 bytes, uint32]
                (no metadata bytes)                          [0 bytes]
```