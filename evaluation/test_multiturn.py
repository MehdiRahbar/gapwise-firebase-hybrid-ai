import unittest
from multiturn_diagnostic import evaluate,play
from logic_engine_v8 import HornEngine
class TestMultiTurn(unittest.TestCase):
    def test_simple_necessary_condition(self):
        row={'rules':"[['goal', 'not a', 'not b']]",'known_facts':'[]','known_untrue_facts':'[]','cannot_ask_facts':'[]','goal':'goal','all_valid_qs':"['a','b']"}
        r=play(row,'horn','least_world',4,1)
        self.assertFalse(r['resolved'])
        self.assertEqual(r['status'],'UNKNOWN')
        self.assertLessEqual(r['steps'],4)
    def test_policies_do_not_access_gt(self):
        row={'rules':"[['goal', 'not a']]",'known_facts':'[]','known_untrue_facts':'[]','cannot_ask_facts':'[]','goal':'goal','all_valid_qs':"['a']",'gt_qs':'NON-JSON MALICIOUS FIELD'}
        result,_details,fail=evaluate([row],strategies=('horn',),modes=('least_world',),budget=2)
        self.assertFalse(fail);self.assertEqual(result[0]['n'],1)
    def test_never_ask_goal(self):
        row={'rules':"[['goal', 'not a']]",'known_facts':'[]','known_untrue_facts':'[]','cannot_ask_facts':'[]','goal':'goal','all_valid_qs':"['a','goal']"}
        self.assertNotIn('goal',HornEngine.from_row(row).candidates)
    def test_adversarial_does_not_invent_impossible_answer(self):
        row={'rules':"[['goal', 'not a']]",'known_facts':"['a']",'known_untrue_facts':'[]','cannot_ask_facts':'[]','goal':'goal','all_valid_qs':"['a']"}
        self.assertTrue(play(row,'horn','adversarial',5,10)['resolved'])
if __name__=='__main__':unittest.main()
