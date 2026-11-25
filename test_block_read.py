import unittest
from block_read import fields,make,batches,unpack,read_batched
from main import address_plan,value
from unittest.mock import patch
from pathlib import Path

class Blocks(unittest.TestCase):
    def fake(self,commands):
        self.calls.extend(commands)
        result={}
        for c in commands:
            area,start,n=fields(c)
            payload=''.join(f'{(a%2 if area=="09" else (a*17)%65536):0{2 if area=="09" else 4}X}' for a in range(start,start+n))
            result[c]={'ok':True,'response':'01010000'+payload}
        return {'plc':'ATIKSU','responses':result}
    def setUp(self):self.calls=[]
    def test_data_equivalence(self):
        cmds=[make('B0',n) for n in (0,1,3,110,111)]+[make('09',n) for n in (1,2,4094,4095,32768,32769)]+[make('89',1),make('82',100)]
        a=read_batched(self.fake,cmds,set());b=read_batched(self.fake,cmds,set(),False)
        self.assertEqual(a['responses'],b['responses']);self.assertLess(a['stats']['commands'],b['stats']['commands'])
        self.assertTrue(all(fields(c)[2]<=16 for c in self.calls))
    def test_bad_response_fallback_and_cache(self):
        cmds=[make('B0',1),make('B0',2),make('09',3),make('09',4)]
        disabled=set()
        def send(cs):
            r=self.fake(cs)
            for c in cs:
                if fields(c)[0]=='B0' and fields(c)[2]>1:r['responses'][c]={'ok':True,'response':'01010000FFFF'}
            return r
        r=read_batched(send,cmds,disabled)
        self.assertEqual(disabled,{'B0'});self.assertEqual(r['stats']['fallback'],2)
        self.assertEqual(r['responses'],self.fake(cmds)['responses'])
        self.assertEqual(read_batched(send,cmds,disabled)['stats']['commands'],3)
    def test_write_and_range_rejected(self):
        for c in ('0102B00001000001','0101B00001000000','0101B00001000011','0101090FFF000002','0101B0FFFF000002','0101B00001010001'):
            with self.assertRaises(ValueError):fields(c)
    def test_bad_flags_rejected(self):
        c=make('09',1,2)
        with self.assertRaises(ValueError):unpack(c,{'ok':True,'response':'010100000102'},[make('09',1)])
    def test_read_targets(self):
        from main import read_targets
        targets={'CIO110.00','CIO110.01','CIO111.00','W10.01','W11.00','D100','T0001','T0002'}
        with patch('main.session.read',side_effect=lambda cdm,cmds,enabled:read_batched(self.fake,cmds,set(),enabled)):
            a,_,s=read_targets('test','ATIKSU',targets,[make('89',1)])
            b,_,_=read_targets('test','ATIKSU',targets,[make('89',1)],enabled=False)
        self.assertEqual(a,b);self.assertEqual(a['D100'],1700);self.assertEqual(a['T0001'],1);self.assertEqual(a['T0002'],0);self.assertLess(s['commands'],s['single'])
    def test_actual_bin_if_available(self):
        from cikis import decode
        from logic import extract
        from diagnosis import addresses
        p=Path(__file__).resolve().parent.parent/'PLC_PROGRAM_20261124_144153_277.bin'
        if not p.exists():self.skipTest('Referans BIN dağıtıma dahil değildir')
        b=p.read_bytes();rows=decode(b);logic=extract(b);self.assertEqual(len(rows),57)
        for targets,expected in [({r[0] for r in rows},(29,18)),({r[0] for r in rows}|addresses('CIO110.00',rows,logic),(33,20))]:
            commands=set()
            for a in targets:
                try:
                    c,_=address_plan(a)
                    if c:commands.add(c)
                except ValueError:pass
            r=read_batched(self.fake,commands,set())
            self.assertEqual((len(commands),r['stats']['commands']),expected)
            self.assertEqual(r['responses'],self.fake(commands)['responses'])
if __name__=='__main__':unittest.main()
