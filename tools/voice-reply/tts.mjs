#!/usr/bin/env node
import fs from 'node:fs';
import path from 'node:path';
import process from 'node:process';
import { MsEdgeTTS, OUTPUT_FORMAT } from 'msedge-tts';

const FORMAT_BY_NAME = {
  webm: OUTPUT_FORMAT.WEBM_24KHZ_16BIT_MONO_OPUS,
  mp3: OUTPUT_FORMAT.AUDIO_24KHZ_48KBITRATE_MONO_MP3,
  mp3_96k: OUTPUT_FORMAT.AUDIO_24KHZ_96KBITRATE_MONO_MP3
};

function parseArgs(argv) {
  const args = {
    voice: 'zh-CN-XiaoxiaoNeural',
    out: '',
    text: '',
    rate: '+0%',
    pitch: '+0Hz',
    format: ''
  };
  for (let i = 2; i < argv.length; i++) {
    const a = argv[i];
    if (a === '--voice') args.voice = argv[++i];
    else if (a === '--out') args.out = argv[++i];
    else if (a === '--text') args.text = argv[++i];
    else if (a === '--rate') args.rate = argv[++i] || '+0%';
    else if (a === '--pitch') args.pitch = argv[++i] || '+0Hz';
    else if (a === '--format') args.format = (argv[++i] || '').toLowerCase();
    else if (a === '--help' || a === '-h') args.help = true;
  }
  return args;
}

function usage() {
  console.log(`Usage:\n  node tts.mjs --text "你好" --out out.mp3 [--voice zh-CN-XiaoxiaoNeural] [--format mp3|mp3_96k|webm] [--rate +0%] [--pitch +0Hz]`);
}

function resolveOutputFormat(args) {
  if (args.format && FORMAT_BY_NAME[args.format]) return FORMAT_BY_NAME[args.format];
  const ext = path.extname(args.out).toLowerCase();
  if (ext === '.mp3') return OUTPUT_FORMAT.AUDIO_24KHZ_48KBITRATE_MONO_MP3;
  if (ext === '.webm') return OUTPUT_FORMAT.WEBM_24KHZ_16BIT_MONO_OPUS;
  return OUTPUT_FORMAT.AUDIO_24KHZ_48KBITRATE_MONO_MP3;
}

async function main() {
  const args = parseArgs(process.argv);
  if (args.help || !args.text || !args.out) {
    usage();
    process.exit(args.help ? 0 : 1);
  }

  fs.mkdirSync(path.dirname(args.out), { recursive: true });

  const tts = new MsEdgeTTS();
  await tts.setMetadata(args.voice, resolveOutputFormat(args));
  const outDir = path.dirname(args.out);
  const { audioFilePath } = await tts.toFile(outDir, args.text, {
    rate: String(args.rate || '+0%'),
    pitch: String(args.pitch || '+0Hz')
  });

  if (audioFilePath !== args.out) {
    fs.renameSync(audioFilePath, args.out);
  }

  console.log(args.out);
}

main().catch((err) => {
  console.error(err?.stack || String(err));
  process.exit(1);
});
