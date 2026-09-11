using System;
using System.Collections.Generic;
using System.IO;
using REE.Unpacker;

namespace REE.Unpacker;

internal static class Program
{
    private static int entrySize;

    public static int Main(string[] args)
    {
        var scanOnly = args.Length > 0 && args[0] == "--scan";
        if (scanOnly) args = args[1..];
        if (args.Length < 3)
        {
            Console.Error.WriteLine("Usage: ReplacerPak [--scan] <pak> <outdir|-> <path1> [path2...]");
            return 2;
        }

        var pakPath = args[0];
        var outDir = args[1];
        var targets = new Dictionary<ulong, string>();

        for (var i = 2; i < args.Length; i++)
        {
            var normalized = args[i].Replace('\\', '/');
            var lower = PakHash.iGetStringHash(normalized.ToLowerInvariant());
            var upper = PakHash.iGetStringHash(normalized.ToUpperInvariant());
            targets[((ulong)upper << 32) | lower] = normalized;
        }

        using var pak = File.OpenRead(pakPath);
        var header = ReadHeader(pak);

        entrySize = header.bMajorVersion switch
        {
            2 => 24,
            4 => 48,
            _ => throw new InvalidDataException($"Unsupported PAK version {header.bMajorVersion}.{header.bMinorVersion}")
        };

        var table = pak.ReadBytes(header.dwTotalFiles * entrySize);
        if (header.wFeature is Features.ENCRYPTED_RESOURCES or Features.DLC_EXTRA_DATA1 or Features.EXTRA_DATA or Features.CHUNKED_RESOURCES or Features.DLC_EXTRA_DATA2)
        {
            if (header.wFeature == Features.EXTRA_DATA)
            {
                pak.Seek(4, SeekOrigin.Current);
            }
            else if (header.wFeature is Features.DLC_EXTRA_DATA1 or Features.DLC_EXTRA_DATA2)
            {
                pak.Seek(9, SeekOrigin.Current);
            }

            var encryptedKey = pak.ReadBytes(128);
            table = PakCipher.iDecryptData(table, encryptedKey);

            if (header.wFeature is Features.CHUNKED_RESOURCES or Features.DLC_EXTRA_DATA2)
            {
                PakChunks.iReadMapTable(pak);
            }
        }

        var found = 0;
        var matches = new List<object>();
        using var reader = new MemoryStream(table);
        for (var i = 0; i < header.dwTotalFiles; i++)
        {
            var entry = ReadEntry(reader, header);
            var key = ((ulong)entry.dwHashNameUpper << 32) | entry.dwHashNameLower;
            if (!targets.TryGetValue(key, out var relativePath))
            {
                continue;
            }

            if (scanOnly)
            {
                matches.Add(new { path = relativePath, size = entry.dwDecompressedSize, compressedSize = entry.dwCompressedSize });
                found++;
                continue;
            }
            var bytes = ExtractEntry(pak, header, entry);
            var fullPath = Path.Combine(outDir, relativePath.Replace('/', Path.DirectorySeparatorChar));
            Directory.CreateDirectory(Path.GetDirectoryName(fullPath)!);
            File.WriteAllBytes(fullPath, bytes);
            Console.WriteLine($"EXTRACTED {relativePath} ({bytes.Length} bytes)");
            found++;
        }

        if (scanOnly)
        {
            var json = System.Text.Json.JsonSerializer.Serialize(matches);
            if (outDir == "-")
            {
                // Keep stdout machine-readable. Diagnostics go to stderr.
                Console.Out.Write(json);
            }
            else
            {
                File.WriteAllText(outDir, json);
            }
            Console.Error.WriteLine($"Found {found}/{targets.Count} target files in {Path.GetFileName(pakPath)}");
            // A patch PAK containing none of the requested resources is a valid scan result.
            return 0;
        }
        Console.WriteLine($"Found {found}/{targets.Count} target files in {Path.GetFileName(pakPath)}");
        return found == targets.Count ? 0 : 1;
    }

    private static PakHeader ReadHeader(Stream pak)
    {
        var header = new PakHeader
        {
            dwMagic = pak.ReadUInt32(),
            bMajorVersion = pak.ReadByte(),
            bMinorVersion = pak.ReadByte(),
            wFeature = (Features)pak.ReadInt16(),
            dwTotalFiles = pak.ReadInt32(),
            dwFingerprint = pak.ReadUInt32()
        };

        if (header.dwMagic != 0x414B504B)
        {
            throw new InvalidDataException("Invalid PAK magic.");
        }

        return header;
    }

    private static PakEntry ReadEntry(Stream reader, PakHeader header)
    {
        var entry = new PakEntry();
        if (header.bMajorVersion == 2 && header.bMinorVersion == 0)
        {
            entry.dwOffset = reader.ReadInt64();
            entry.dwDecompressedSize = reader.ReadInt64();
            entry.dwHashNameLower = reader.ReadUInt32();
            entry.dwHashNameUpper = reader.ReadUInt32();
            entry.dwCompressedSize = 0;
            entry.wCompressionType = Compression.NONE;
            entry.dwChecksum = 0;
        }
        else
        {
            entry.dwHashNameLower = reader.ReadUInt32();
            entry.dwHashNameUpper = reader.ReadUInt32();
            entry.dwOffset = reader.ReadInt64();
            entry.dwCompressedSize = reader.ReadInt64();
            entry.dwDecompressedSize = reader.ReadInt64();
            entry.dwAttributes = reader.ReadInt64();
            entry.dwChecksum = reader.ReadUInt64();
            entry.wCompressionType = (Compression)(entry.dwAttributes & 0xF);
            entry.wEncryptionType = (Encryption)((entry.dwAttributes & 0x00FF0000) >> 16);
        }

        return entry;
    }

    private static byte[] ExtractEntry(FileStream pak, PakHeader header, PakEntry entry)
    {
        pak.Seek(entry.dwOffset, SeekOrigin.Begin);

        if (entry.wCompressionType == Compression.NONE)
        {
            if (header.wFeature is Features.CHUNKED_RESOURCES or Features.DLC_EXTRA_DATA2 &&
                (entry.dwAttributes == 0x1000000 || entry.dwAttributes == 0x1000400))
            {
                return PakChunks.iUnwrapChunks(pak, entry);
            }

            return pak.ReadBytes((int)entry.dwCompressedSize);
        }

        var src = pak.ReadBytes((int)entry.dwCompressedSize);
        if (entry.wEncryptionType != Encryption.None && entry.wEncryptionType <= Encryption.Type_Invalid)
        {
            src = ResourceCipher.iDecryptResource(src);
        }

        return entry.wCompressionType switch
        {
            Compression.DEFLATE => DEFLATE.iDecompress(src),
            Compression.ZSTD => ZSTD.iDecompress(src),
            _ => throw new InvalidDataException($"Unknown compression type {entry.wCompressionType}")
        };
    }
}
