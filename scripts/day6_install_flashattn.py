"""Install the verified ABI-matched wheel and compare its GPU result with PyTorch."""

import hashlib
import json
from pathlib import Path
import subprocess
import sys
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]


def main():
    info = json.loads((ROOT / 'reports/day6_flash_attn_assets.json').read_text())
    name = Path(urlsplit(info['source_url']).path).name
    wheel = ROOT / 'wheels' / name
    if hashlib.sha256(wheel.read_bytes()).hexdigest() != info['sha256']:
        raise SystemExit('FlashAttention wheel checksum mismatch')
    result = subprocess.run([sys.executable, '-m', 'pip', 'install', '--no-deps', str(wheel)], timeout=180)
    if result.returncode:
        return result.returncode
    import torch
    import torch.nn.functional as functional
    import flash_attn
    from flash_attn import flash_attn_func
    torch.manual_seed(17)
    q, k, v = [torch.randn(1, 32, 4, 64, dtype=torch.bfloat16, device='cuda') for _ in range(3)]
    actual = flash_attn_func(q, k, v, causal=True)
    expected = functional.scaled_dot_product_attention(q.transpose(1, 2), k.transpose(1, 2),
                                                      v.transpose(1, 2), is_causal=True).transpose(1, 2)
    torch.testing.assert_close(actual, expected, rtol=0.03, atol=0.03)
    torch.cuda.synchronize()
    report = {'wheel_sha256_verified': True, 'flash_attn': flash_attn.__version__,
              'torch': torch.__version__, 'cpp_abi': torch._C._GLIBCXX_USE_CXX11_ABI,
              'bf16_cuda_forward_matches_torch': True, 'complete': True}
    (ROOT / 'reports/day6_flash_attn_verification.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
