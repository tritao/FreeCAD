#include <gtest/gtest.h>

#include <QColor>
#include <QtCore/Qt>
#include <BRep_Builder.hxx>
#include <BRepBuilderAPI_MakePolygon.hxx>
#include <gp_Pnt.hxx>
#include <TopoDS_Compound.hxx>
#include <TopoDS_Wire.hxx>

#include "Mod/TechDraw/App/LineFormat.h"
#include "Mod/TechDraw/App/ProjectionAlgos.h"
#include "src/App/InitApplication.h"

class TestLineFormat: public ::testing::Test
{
protected:
    static void SetUpTestSuite()
    {
        tests::initApplication();
    }
    void SetUp() override
    {
        _lineFormat = std::make_unique<TechDraw::LineFormat>(
            Qt::SolidLine,
            0.5,
            Base::Color(0.0F, 0.0F, 0.0F, 1.0F),
            true
        );
    }
    void TearDown() override
    {

        _lineFormat.reset();
    }

    /// Get a non-owning pointer to the internal LineFormat for this test
    TechDraw::LineFormat* lineFormat()
    {
        return _lineFormat.get();
    }

private:
    std::unique_ptr<TechDraw::LineFormat> _lineFormat;
};


TEST_F(TestLineFormat, setQColorKeepsOpaqueColorsOpaque)
{
    auto format = lineFormat();

    format->setQColor(QColor(255, 0, 0, 255));

    const Base::Color stored = format->getColor();
    EXPECT_FLOAT_EQ(stored.r, 1.0F);
    EXPECT_FLOAT_EQ(stored.g, 0.0F);
    EXPECT_FLOAT_EQ(stored.b, 0.0F);
    EXPECT_FLOAT_EQ(stored.a, 1.0F);

    const QColor roundTripped = format->getQColor();
    EXPECT_EQ(roundTripped.red(), 255);
    EXPECT_EQ(roundTripped.green(), 0);
    EXPECT_EQ(roundTripped.blue(), 0);
    EXPECT_EQ(roundTripped.alpha(), 255);
}

TEST_F(TestLineFormat, setQColorPreservesAlphaValue)
{
    auto format = lineFormat();

    format->setQColor(QColor(12, 34, 56, 78));

    const QColor roundTripped = format->getQColor();
    EXPECT_EQ(roundTripped.red(), 12);
    EXPECT_EQ(roundTripped.green(), 34);
    EXPECT_EQ(roundTripped.blue(), 56);
    EXPECT_EQ(roundTripped.alpha(), 78);
}

TEST(ProjectionAlgos, joinsConnectedLinearEdgesInOnePath)
{
    BRepBuilderAPI_MakePolygon polygon;
    polygon.Add(gp_Pnt(0, 0, 0));
    polygon.Add(gp_Pnt(100, 0, 0));
    polygon.Add(gp_Pnt(100, 100, 0));

    const auto svg = TechDraw::ProjectionAlgos::getSVGPath(
        polygon.Wire(),
        Base::Vector3d(0, 0, 1),
        {{"stroke-linejoin", "miter"}});

    EXPECT_EQ(svg.find("<path"), svg.rfind("<path"));
    EXPECT_NE(svg.find("L 100 0"), std::string::npos);
    EXPECT_NE(svg.find("L 100 100"), std::string::npos);
    EXPECT_NE(svg.find("stroke-linejoin=\"miter\""), std::string::npos);
}

TEST(ProjectionAlgos, preservesIndependentClosedWireBoundaries)
{
    BRepBuilderAPI_MakePolygon first;
    first.Add(gp_Pnt(0, 0, 0));
    first.Add(gp_Pnt(100, 0, 0));
    first.Add(gp_Pnt(100, 100, 0));
    first.Add(gp_Pnt(0, 100, 0));
    first.Close();

    BRepBuilderAPI_MakePolygon second;
    second.Add(gp_Pnt(100, 100, 0));
    second.Add(gp_Pnt(200, 100, 0));
    second.Add(gp_Pnt(200, 200, 0));
    second.Add(gp_Pnt(100, 200, 0));
    second.Close();

    BRep_Builder builder;
    TopoDS_Compound compound;
    builder.MakeCompound(compound);
    builder.Add(compound, first.Wire());
    builder.Add(compound, first.Wire());
    builder.Add(compound, second.Wire());

    const auto svg = TechDraw::ProjectionAlgos::getSVGPath(
        compound,
        Base::Vector3d(0, 0, 1));

    const auto firstPath = svg.find("<path");
    const auto secondPath = svg.find("<path", firstPath + 1);
    EXPECT_NE(firstPath, std::string::npos);
    EXPECT_NE(secondPath, std::string::npos);
    EXPECT_EQ(std::string::npos, svg.find("<path", secondPath + 1));
}
