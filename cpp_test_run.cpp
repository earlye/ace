#include <ace/run_test.hpp>

#include <iostream>
#include <typeinfo>

namespace ace
{
  void run_test(test const& current_test, stats& statistics)
  {
    std::cout << "--- \"" << current_test.name_ << "\"" << std::endl;
    try
      {
        current_test.fn_();
        std::cout << "test \"" << current_test.name_ << "\" PASSED" << std::endl;
        ++statistics.pass_count;
      }
    catch( std::exception& e )
      {
        std::cerr << "test \"" << current_test.name_ << "\" FAILED:\n" << e.what() << ":" << typeid(e).name() << std::endl;
        ++statistics.fail_count;
      }
    catch( ... )
      {
        std::cerr << "test \"" << current_test.name_ << "\" FAILED:\n" << std::endl;
        ++statistics.fail_count;
      }
  }
}
