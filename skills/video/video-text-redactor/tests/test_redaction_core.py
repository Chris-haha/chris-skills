import sys
from pathlib import Path
import numpy as np
import cv2
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
try:
 import redaction_core as core
except ImportError:
 core=None

def test_module_is_available():
 assert core is not None, '缺少可运行的脱敏实现'

@pytest.mark.skipif(core is None,reason='implementation missing')
def test_unicode_match_and_keep_exclusions():
 rule={'terms':['张三 AI','Alice'], 'regex':['[\\w.+-]+@[\\w.-]+\\.[A-Za-z]{2,}'], 'exclude':['保留 Alice']}
 assert core.match_spans('张三ＡＩ 分享',rule)==[(0,4,'张三 AI')]
 assert core.match_spans('保留 Alice',rule)==[]
 assert core.match_spans('mail: a.b@test.cn',rule)==[(6,17,'regex:0')]

@pytest.mark.skipif(core is None,reason='implementation missing')
def test_substring_boxes_and_edge_padding():
 obs={'text':'你好张三','box':[0,0,80,20],'chars':[[0,0,20,20],[20,0,20,20],[40,0,20,20],[60,0,20,20]]}
 assert core.span_box(obs,2,4)==[40,0,40,20]
 assert core.pad_box([-2,-2,10,10],(100,50),8)==[0,0,16,16]

@pytest.mark.skipif(core is None,reason='implementation missing')
def test_pixelate_irreversibly_removes_source_glyphs():
 rng=np.random.default_rng(3);im=rng.integers(0,255,(80,160,3),dtype=np.uint8);out=im.copy()
 core.obscure(out,[20,10,100,40],mode='solid')
 assert np.all(out[10:50,20:120]==24)
 assert np.array_equal(out[:10],im[:10])
 out=im.copy();core.obscure(out,[20,10,100,40],mode='mosaic')
 assert len(np.unique(out[10:50,20:120].reshape(-1,3),axis=0))<=8

@pytest.mark.skipif(core is None,reason='implementation missing')
def test_affine_tracker_follows_zoom_and_pan():
 rng=np.random.default_rng(4);a=rng.integers(0,256,(300,480),dtype=np.uint8)
 M=np.float32([[1.08,0,14],[0,1.08,7]])
 b=cv2.warpAffine(a,M,(480,300))
 tracked=core.track_box(a,b,[110,80,130,60])
 assert tracked is not None
 assert np.max(np.abs(np.array(tracked)-[132.8,93.4,140.4,64.8]))<5

@pytest.mark.skipif(core is None,reason='implementation missing')
def test_cut_is_detected_but_static_is_not():
 a=np.zeros((100,180),np.uint8);b=np.full_like(a,240)
 assert core.is_cut(a,b)
 assert not core.is_cut(a,a)

@pytest.mark.skipif(core is None,reason='implementation missing')
def test_rules_snapshot_is_idempotent_and_empty_targets_rejected(tmp_path):
 import video_text_redactor as tool
 import json
 p=tmp_path/'rules.json';p.write_text(json.dumps({'version':1,'presets':['email']}))
 a=tool.read_rules(p);p.write_text(json.dumps(a));b=tool.read_rules(p)
 assert a==b
 p.write_text(json.dumps({'version':1}))
 with pytest.raises(ValueError,match='No targets'):tool.read_rules(p)

@pytest.mark.skipif(core is None,reason='implementation missing')
def test_normalization_keeps_original_codepoint_offsets():
 assert core.match_spans('Ａß 张 三',{'terms':['ass 张三']})==[(0,6,'ass 张三')]
 # No character boxes is a full-line conservative fallback, not guessed widths.
 assert core.span_box({'text':'ABC 张三','box':[10,10,200,20]},4,6)==[10,10,200,20]

@pytest.mark.skipif(core is None,reason='implementation missing')
def test_fallback_padding_stays_bounded_during_ocr_loss():
 assert hasattr(core,'fallback_box'), '缺失跟踪丢失后的有界扩框，连续失效会递归膨胀'
 for age in range(1,121):
  b=core.fallback_box([300,200,100,40],age,(1280,720))
  assert b[2]<=160 and b[3]<=100

@pytest.mark.skipif(core is None,reason='implementation missing')
def test_ocr_alias_correction_replaces_the_same_physical_track():
 assert hasattr(core,'same_target_area'), '不同 OCR 别名不应积累成重叠旧轨迹'
 assert core.same_target_area([20,10,100,30],[22,9,98,32])
 assert core.same_target_area([20,10,100,30],[20,10,70,30])
 assert not core.same_target_area([20,10,100,30],[400,10,100,30])

@pytest.mark.skipif(core is None,reason='implementation missing')
def test_tracker_rejects_runaway_growth_relative_to_last_ocr_anchor():
 assert hasattr(core,'valid_track_size'), '需限制连续跟踪漂移，不能每帧合理但累计变成巨框'
 assert core.valid_track_size([10,10,120,30],[20,20,150,38])
 assert not core.valid_track_size([10,10,120,30],[20,20,700,600])
