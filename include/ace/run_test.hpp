#ifndef h8b81c7c0_04aa_4399_b952_e4e4fb9a0323
#define h8b81c7c0_04aa_4399_b952_e4e4fb9a0323

namespace ace
{
  typedef void (*test_fn)();
  struct test
  {
    test_fn fn_;
    char const* name_;
  };

  struct stats
  {
    int pass_count;
    int fail_count;
  };

  void run_test(test const& function, stats& statistics);
}
#endif
